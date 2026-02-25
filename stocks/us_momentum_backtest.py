#!/usr/bin/env python3
"""
미국 주식 모멘텀 상위 전략 스캐너 + 간단 백테스트

목표:
- yfinance 데이터로 미주 종목들 모멘텀 스코어를 계산하고
- 상위 N개(≈상위 1% 수준)를 뽑아서
- 월간 리밸런싱 포트폴리오를 간단히 백테스트.

실행 예시:
    .venv/bin/python stocks/us_momentum_backtest.py scan
    .venv/bin/python stocks/us_momentum_backtest.py backtest
"""

import sys
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.supabase_client import get_supabase


# ─────────────────────────────────────────────
# 유니버스 정의 (파일/웹 연동 전까지 파일 내 상수로 관리)
# ─────────────────────────────────────────────
# 대형 성장주 + 섹터 대표주 위주 50종 정도
US_UNIVERSE = [
    # Mega-cap tech / growth
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA",
    "AVGO", "ADBE", "NFLX", "ORCL", "CRM",
    # Semis
    "AMD", "INTC", "QCOM", "MU", "AMAT", "LRCX", "ASML",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C",
    # Healthcare
    "LLY", "JNJ", "MRK", "ABBV", "PFE", "UNH",
    # Consumer / retail
    "HD", "LOW", "COST", "TGT", "MCD", "SBUX", "NKE",
    # Industrials / energy / materials
    "CAT", "BA", "GE", "HON", "XOM", "CVX",
    # ETFs (섹터/지수 대표)
    "SPY", "QQQ", "XLK", "XLF", "XLE", "XLV",
]


@dataclass
class MomentumScore:
    symbol: str
    score: float
    ret_5d: float
    ret_20d: float
    vol_ratio: float
    near_high: float


# ─────────────────────────────────────────────
# 환경 / Supabase
# ─────────────────────────────────────────────
load_env()
supabase = get_supabase()


def calc_momentum_score_for_series(
    symbol: str,
    closes: pd.Series,
    highs: pd.Series,
    volumes: pd.Series,
) -> MomentumScore | None:
    """국내 calc_momentum_score와 동일한 로직을 yfinance 시리즈에 적용."""
    if len(closes) < 21 or closes.isna().any():
        return None

    closes = closes.dropna()
    highs = highs.reindex_like(closes).ffill()
    volumes = volumes.reindex_like(closes).fillna(0)

    if len(closes) < 21:
        return None

    price = float(closes.iloc[-1])

    # 1. 수익률 모멘텀 (가중치 40%)
    try:
        ret_5d = (closes.iloc[-1] / closes.iloc[-6] - 1) * 100 if len(closes) >= 6 else 0.0
        ret_20d = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100 if len(closes) >= 21 else 0.0
    except Exception:
        return None

    momentum_raw = ret_5d * 0.6 + ret_20d * 0.4
    momentum_score = max(0, min(100, 50 + momentum_raw * 5))

    # 2. 거래량 모멘텀 (가중치 30%)
    vol_5 = float(volumes.tail(5).mean())
    vol_20 = float(volumes.tail(20).mean() if len(volumes) >= 20 else vol_5)
    vol_ratio = (vol_5 / vol_20) if vol_20 > 0 else 1.0
    vol_score = max(0, min(100, vol_ratio * 50))

    # 3. 신고가 근접도 (가중치 30%)
    high_60d = float(highs.tail(60).max() if len(highs) >= 1 else price)
    nearness = (price / high_60d) * 100 if high_60d > 0 else 50.0
    high_score = max(0, min(100, (nearness - 80) * 5))

    total = momentum_score * 0.4 + vol_score * 0.3 + high_score * 0.3

    return MomentumScore(
        symbol=symbol,
        score=round(total, 1),
        ret_5d=round(ret_5d, 2),
        ret_20d=round(ret_20d, 2),
        vol_ratio=round(vol_ratio, 2),
        near_high=round(nearness, 1),
    )


def scan_today_top_us(
    universe: List[str] = US_UNIVERSE,
    lookback_days: int = 90,
    top_percent: float = 1.0,
) -> List[MomentumScore]:
    """
    오늘 기준 미주 모멘텀 상위 종목 스캔.

    - lookback_days: 모멘텀 계산용 과거 일수
    - top_percent: 상위 n% (1.0 → 상위 1%)
    """
    if not universe:
        print("❌ 유니버스가 비어 있습니다.")
        return []

    tickers = sorted(set(universe))
    print(f"📡 US 모멘텀 스캔: {len(tickers)}종, lookback={lookback_days}일")

    data = yf.download(
        tickers=tickers,
        period=f"{lookback_days + 40}d",
        auto_adjust=False,
        progress=False,
        group_by="column",
    )

    if data.empty:
        print("❌ yfinance 데이터가 비었습니다.")
        return []

    closes = data["Adj Close"]
    highs = data["High"]
    volumes = data["Volume"]

    scores: List[MomentumScore] = []
    for sym in tickers:
        if sym not in closes.columns:
            continue
        s = calc_momentum_score_for_series(
            symbol=sym,
            closes=closes[sym].dropna(),
            highs=highs[sym].dropna(),
            volumes=volumes[sym].dropna(),
        )
        if s is not None:
            scores.append(s)

    if not scores:
        print("❌ 스코어 계산 결과가 없습니다.")
        return []

    scores.sort(key=lambda x: x.score, reverse=True)
    n_universe = len(scores)
    n_top = max(1, int(round(n_universe * (top_percent / 100.0))))  # 상위 n%

    top_scores = scores[:n_top]

    print(f"🎯 상위 {top_percent:.2f}% ≈ {n_top}개 종목")
    for i, s in enumerate(top_scores, start=1):
        print(
            f"{i:>2}. {s.symbol:<6} | 점수 {s.score:>5.1f} | "
            f"5일 {s.ret_5d:+6.2f}% | 20일 {s.ret_20d:+6.2f}% | "
            f"Vol {s.vol_ratio:>4.2f}x | 60일高 근접 {s.near_high:>5.1f}%"
        )

    # Supabase에 전체 유니버스 점수 저장 (대시보드에서 랭킹 표시용)
    save_all_to_supabase(scores)

    return top_scores


def save_all_to_supabase(all_scores: List[MomentumScore]) -> None:
    """전체 유니버스 점수를 Supabase us_momentum_signals 테이블에 저장."""
    if not supabase:
        print("⚠️ Supabase 미설정. DB 저장 건너뜀.")
        return

    if not all_scores:
        return

    run_date = datetime.utcnow().date().isoformat()
    table = "us_momentum_signals"

    try:
        supabase.table(table).delete().eq("run_date", run_date).execute()
    except Exception as e:
        print(f"⚠️ Supabase delete 실패: {e}")

    rows = []
    for s in all_scores:
        rows.append(
            {
                "run_date": run_date,
                "symbol": s.symbol,
                "score": s.score,
                "ret_5d": s.ret_5d,
                "ret_20d": s.ret_20d,
                "vol_ratio": s.vol_ratio,
                "near_high": s.near_high,
            }
        )

    try:
        supabase.table(table).insert(rows).execute()
        print(f"✅ Supabase us_momentum_signals 저장 완료 ({len(rows)}건, run_date={run_date})")
    except Exception as e:
        print(f"⚠️ Supabase insert 실패: {e}")


def _build_rebalance_dates(index: pd.DatetimeIndex, every_n_days: int = 21) -> List[pd.Timestamp]:
    """리밸런싱 기준일 (약 월 1회) 생성."""
    if len(index) < 60:
        return []
    dates: List[pd.Timestamp] = []
    i = 60  # 모멘텀 계산에 최소 60일 확보 후 시작
    while i < len(index):
        dates.append(index[i])
        i += every_n_days
    if index[-1] not in dates:
        dates.append(index[-1])
    return dates


def backtest_monthly_rotation(
    universe: List[str] = US_UNIVERSE,
    years: int = 2,
    top_percent: float = 1.0,
) -> Dict:
    """
    간단한 월간 모멘텀 로테이션 백테스트.

    - 매 리밸런싱 시점마다 모멘텀 스코어 상위 n% 종목을 동일비중 매수
    - 다음 리밸런싱 때까지 홀딩
    """
    if not universe:
        print("❌ 유니버스가 비어 있습니다.")
        return {}

    tickers = sorted(set(universe))
    initial_capital = 100_000.0
    print(f"📊 US 모멘텀 로테이션 백테스트 — {years}년, 초기 {initial_capital:,.0f} USD, "
          f"{len(tickers)}종, 상위 {top_percent:.2f}%")

    data = yf.download(
        tickers=tickers,
        period=f"{years}y",
        auto_adjust=False,
        progress=False,
        group_by="column",
    )
    if data.empty:
        print("❌ yfinance 데이터가 비었습니다.")
        return {}

    closes = data["Adj Close"].dropna(how="all")
    highs = data["High"].reindex_like(closes)
    volumes = data["Volume"].reindex_like(closes)

    dates = closes.index
    rebalance_dates = _build_rebalance_dates(dates)
    if len(rebalance_dates) < 2:
        print("❌ 리밸런싱 기준일이 부족합니다.")
        return {}

    capital = initial_capital
    portfolio_value_history: List[Tuple[pd.Timestamp, float]] = []
    current_positions: Dict[str, float] = {}  # symbol -> shares

    for i, reb_date in enumerate(rebalance_dates):
        # 포트폴리오 평가
        if i > 0:
            reb_idx = dates.get_loc(reb_date)
            prev_date = rebalance_dates[i - 1]
            prev_idx = dates.get_loc(prev_date)
            price_row = closes.iloc[reb_idx]
            value = 0.0
            for sym, shares in current_positions.items():
                px = price_row.get(sym, np.nan)
                if not np.isnan(px):
                    value += shares * float(px)
            capital = value if value > 0 else capital
            portfolio_value_history.append((reb_date, capital))

        # 새 포트폴리오 구성
        reb_idx = dates.get_loc(reb_date)
        window_start = max(0, reb_idx - 60)
        window_closes = closes.iloc[window_start: reb_idx + 1]
        window_highs = highs.iloc[window_start: reb_idx + 1]
        window_vols = volumes.iloc[window_start: reb_idx + 1]

        scores: List[MomentumScore] = []
        for sym in tickers:
            if sym not in window_closes.columns:
                continue
            s = calc_momentum_score_for_series(
                symbol=sym,
                closes=window_closes[sym].dropna(),
                highs=window_highs[sym].dropna(),
                volumes=window_vols[sym].dropna(),
            )
            if s is not None:
                scores.append(s)

        if not scores:
            continue

        scores.sort(key=lambda x: x.score, reverse=True)
        n_universe = len(scores)
        n_top = max(1, int(round(n_universe * (top_percent / 100.0))))
        top_scores = scores[:n_top]

        # 동일비중 매수
        alloc_per_stock = capital / n_top
        new_positions: Dict[str, float] = {}
        reb_prices = closes.iloc[reb_idx]
        for s in top_scores:
            price = float(reb_prices.get(s.symbol, np.nan))
            if not price or np.isnan(price):
                continue
            shares = alloc_per_stock / price
            if shares <= 0:
                continue
            new_positions[s.symbol] = shares

        current_positions = new_positions

    if not portfolio_value_history:
        print("❌ 포트폴리오 히스토리가 비었습니다.")
        return {}

    dates_arr = [d for d, _ in portfolio_value_history]
    values_arr = np.array([v for _, v in portfolio_value_history], dtype=float)
    final_value = float(values_arr[-1])
    total_return = (final_value / initial_capital - 1.0) * 100.0

    # 단순 MDD 계산
    peak = -np.inf
    max_dd = 0.0
    for v in values_arr:
        if v > peak:
            peak = v
        dd = (v / peak - 1.0) * 100.0
        max_dd = min(max_dd, dd)

    print("\n" + "=" * 50)
    print(f"기간: {dates_arr[0].date()} ~ {dates_arr[-1].date()} "
          f"({len(dates_arr)} 포인트)")
    print(f"초기 자본:  {initial_capital:>10,.2f} USD")
    print(f"최종 자본:  {final_value:>10,.2f} USD")
    print(f"총 수익률: {total_return:>9.2f}%")
    print(f"최대 낙폭: {max_dd:>9.2f}%")
    print("=" * 50)

    return {
        "initial_capital": initial_capital,
        "final_capital": final_value,
        "total_return_pct": total_return,
        "max_drawdown_pct": max_dd,
        "points": len(dates_arr),
        "start_date": dates_arr[0],
        "end_date": dates_arr[-1],
    }


def main():
    mode = "scan"
    if len(sys.argv) > 1:
        mode = sys.argv[1].strip().lower()

    if mode == "scan":
        scan_today_top_us()
    elif mode == "backtest":
        backtest_monthly_rotation()
    else:
        print("사용법:")
        print("  .venv/bin/python stocks/us_momentum_backtest.py scan")
        print("  .venv/bin/python stocks/us_momentum_backtest.py backtest")


if __name__ == "__main__":
    main()

