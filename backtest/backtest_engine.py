"""BTC 백테스트 엔진 — Phase 13+ 전략 검증

BTC 자동매매 전략을 과거 데이터에 적용하여 성과를 측정한다.
- OHLCV: Supabase btc_ohlcv 테이블 → 없으면 yfinance 1년치
- 전략: 복합스코어 ≥ 45 진입 / -3% SL / +12% TP / 부분익절 / 트레일링
- 결과: JSON + PNG (수익곡선 + 드로다운) → backtest/results/ 저장

Usage:
    python backtest/backtest_engine.py [--days 365] [--no-save] [--output-dir PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # 서버 환경 — 디스플레이 없음
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# ── sys.path ──────────────────────────────────────────────────────────────────
_WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_WORKSPACE))

from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase

load_env()
log = get_logger("backtest")

# ── 결과 저장 경로 ─────────────────────────────────────────────────────────────
_DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"

# ── 전략 파라미터 (btc_trading_agent.py RISK 동일) ────────────────────────────
RISK = {
    "invest_ratio":      0.30,
    "stop_loss":        -0.03,
    "take_profit":       0.12,
    "partial_tp_pct":    0.08,    # 부분익절 기준 수익률
    "partial_tp_ratio":  0.50,    # 부분익절 시 50% 매도
    "trailing_stop":     0.02,    # 피크 대비 2% 하락 시 손절
    "trailing_activate": 0.015,   # 트레일링 활성화 수익률 임계
    "buy_composite_min": 45,
    "fee":               0.001,   # 업비트 수수료 (매수/매도 동일)
    "timecut_days":      7,
}


# ── 복합 스코어 (btc_trading_agent.py calc_btc_composite 인라인) ────────────────

def _calc_composite(
    fg_value: int,
    rsi_d: float,
    bb_pct: float,
    vol_ratio_d: float,
    trend: str,
    ret_7d: float = 0.0,
    regime: str = "TRANSITION",
) -> int:
    """BTC 복합 스코어 계산 (온체인 데이터 없이, NEUTRAL 기본값).

    btc_trading_agent.py의 calc_btc_composite를 인라인 복제.
    펀딩비/OI/롱숏비율/김치프리미엄은 과거 데이터 없어 NEUTRAL 처리.
    """
    # F&G (낮을수록 매수 기회)
    if fg_value <= 10:   fg_sc = 22
    elif fg_value <= 20: fg_sc = 18
    elif fg_value <= 30: fg_sc = 13
    elif fg_value <= 45: fg_sc = 7
    elif fg_value <= 55: fg_sc = 3
    else:                fg_sc = 0

    # 일봉 RSI
    if rsi_d <= 30:   rsi_sc = 20
    elif rsi_d <= 38: rsi_sc = 16
    elif rsi_d <= 45: rsi_sc = 12
    elif rsi_d <= 55: rsi_sc = 6
    elif rsi_d <= 65: rsi_sc = 2
    else:             rsi_sc = 0

    # BB 포지션 (0%=하단, 100%=상단)
    if bb_pct <= 10:   bb_sc = 12
    elif bb_pct <= 25: bb_sc = 9
    elif bb_pct <= 40: bb_sc = 6
    elif bb_pct <= 55: bb_sc = 2
    else:              bb_sc = 0

    # 거래량 비율
    if vol_ratio_d >= 2.0:   vol_sc = 10
    elif vol_ratio_d >= 1.5: vol_sc = 8
    elif vol_ratio_d >= 1.0: vol_sc = 5
    elif vol_ratio_d >= 0.6: vol_sc = 2
    else:                    vol_sc = 0

    # 추세
    if trend == "UPTREND":    tr_sc = 12
    elif trend == "SIDEWAYS": tr_sc = 6
    else:                     tr_sc = 0

    # 온체인 데이터 없음 → NEUTRAL
    funding_sc = 3   # NEUTRAL = 3점
    ls_sc      = 2   # NEUTRAL = 2점
    oi_sc      = 2   # OI_NORMAL = 2점

    # 7일 수익률 보너스
    bonus = 0
    if ret_7d <= -15:  bonus = 5
    elif ret_7d <= -10: bonus = 3
    if ret_7d > 0 and trend == "UPTREND":
        bonus += 2
    elif ret_7d < -5 and trend == "DOWNTREND":
        bonus -= 3

    # 레짐 조정
    _regime_map = {"RISK_ON": +5, "TRANSITION": 0, "RISK_OFF": -10, "CRISIS": -20}
    regime_adj = _regime_map.get(str(regime).upper(), 0)

    raw = (fg_sc + rsi_sc + bb_sc + vol_sc + tr_sc
           + funding_sc + ls_sc + oi_sc + bonus + regime_adj)
    return max(0, min(int(raw), 100))


# ── 보조 지표 계산 ────────────────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _bb_pct(close: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.Series:
    """볼린저 밴드 %B (0=하단, 100=상단)."""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    band_width = upper - lower
    pct = ((close - lower) / band_width.replace(0, float("nan"))) * 100
    return pct.clip(0, 100)


def _trend(close: pd.Series) -> pd.Series:
    """EMA20/EMA50 교차로 추세 판단."""
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    conditions = [
        ema20 > ema50 * 1.01,
        ema20 < ema50 * 0.99,
    ]
    choices = ["UPTREND", "DOWNTREND"]
    return pd.Series(
        np.select(conditions, choices, default="SIDEWAYS"),
        index=close.index,
    )


def _vol_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    avg = volume.rolling(period).mean()
    return volume / avg.replace(0, float("nan"))


def _ret_7d(close: pd.Series) -> pd.Series:
    return close.pct_change(7) * 100


# ── 데이터 수집 ────────────────────────────────────────────────────────────────

def _fetch_fg_historical(limit: int = 400) -> Dict[str, int]:
    """alternative.me F&G 히스토리 (날짜 → 값 dict, ISO 날짜 키)."""
    import requests as _req
    try:
        url = f"https://api.alternative.me/fng/?limit={limit}&format=json"
        res = _req.get(url, timeout=10)
        data = res.json().get("data", [])
        result: Dict[str, int] = {}
        for item in data:
            ts = int(item.get("timestamp", 0))
            val = int(item.get("value", 50))
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            result[date_str] = val
        log.info(f"F&G 히스토리 {len(result)}개 수집")
        return result
    except Exception as e:
        log.warning(f"F&G 히스토리 수집 실패: {e}")
        return {}


def _fetch_ohlcv_supabase(days: int) -> Optional[pd.DataFrame]:
    """Supabase btc_ohlcv 테이블에서 OHLCV 조회.

    컬럼 예상: date(text), open, high, low, close, volume
    없거나 행 부족 시 None 반환 → yfinance fallback 사용.
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return None
        start = (datetime.now(timezone.utc) - timedelta(days=days + 10)).date().isoformat()
        res = (
            supabase.table("btc_ohlcv")
            .select("date,open,high,low,close,volume")
            .gte("date", start)
            .order("date")
            .execute()
        )
        rows = res.data or []
        if len(rows) < 30:
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"])
        log.info(f"Supabase OHLCV {len(df)}행 로드")
        return df
    except Exception as e:
        log.warning(f"Supabase OHLCV 조회 실패: {e}")
        return None


def _fetch_ohlcv_yfinance(days: int) -> pd.DataFrame:
    """yfinance에서 BTC-USD OHLCV 수집 (fallback)."""
    import yfinance as yf
    ticker = yf.Ticker("BTC-USD")
    period = f"{max(days, 365)}d"
    df = ticker.history(period=period, interval="1d")
    if df.empty:
        raise RuntimeError("yfinance BTC-USD 데이터 없음")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df = df.dropna(subset=["close"])
    log.info(f"yfinance OHLCV {len(df)}행 로드 (BTC-USD)")
    return df


def load_ohlcv(days: int) -> pd.DataFrame:
    df = _fetch_ohlcv_supabase(days)
    if df is None or len(df) < 30:
        log.info("Supabase OHLCV 부족 → yfinance 사용")
        df = _fetch_ohlcv_yfinance(days)
    # 마지막 days개 행만 사용
    return df.tail(days + 50)  # 여유분 확보 (지표 초기화용)


# ── 시그널 데이터프레임 구성 ───────────────────────────────────────────────────

def build_signal_df(df: pd.DataFrame, fg_map: Dict[str, int]) -> pd.DataFrame:
    """기술 지표 + F&G + 복합스코어 계산."""
    df = df.copy()
    df["rsi"] = _rsi(df["close"])
    df["bb_pct"] = _bb_pct(df["close"])
    df["trend"] = _trend(df["close"])
    df["vol_ratio"] = _vol_ratio(df["volume"])
    df["ret_7d"] = _ret_7d(df["close"])

    # F&G 매핑 (없는 날짜는 50=중립)
    dates = df.index.strftime("%Y-%m-%d")
    df["fg"] = [fg_map.get(d, 50) for d in dates]

    # 복합 스코어
    scores = []
    for _, row in df.iterrows():
        if pd.isna(row.get("rsi")) or pd.isna(row.get("bb_pct")):
            scores.append(0)
            continue
        s = _calc_composite(
            fg_value=int(row["fg"]),
            rsi_d=float(row["rsi"]),
            bb_pct=float(row["bb_pct"]),
            vol_ratio_d=float(row["vol_ratio"]) if not pd.isna(row["vol_ratio"]) else 1.0,
            trend=str(row["trend"]),
            ret_7d=float(row["ret_7d"]) if not pd.isna(row["ret_7d"]) else 0.0,
        )
        scores.append(s)
    df["composite"] = scores
    return df


# ── 매매 시뮬레이션 ────────────────────────────────────────────────────────────

class Position:
    """오픈 포지션 상태."""
    __slots__ = (
        "entry_date", "entry_price", "qty", "invested",
        "partial_done", "peak_price", "trailing_active",
    )

    def __init__(self, entry_date: str, entry_price: float, qty: float, invested: float):
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.qty = qty
        self.invested = invested
        self.partial_done = False
        self.peak_price = entry_price
        self.trailing_active = False


class Trade:
    """완료된 거래 기록."""
    __slots__ = (
        "entry_date", "exit_date", "entry_price", "exit_price",
        "pnl_pct", "pnl_krw", "exit_reason",
    )

    def __init__(self, entry_date: str, exit_date: str,
                 entry_price: float, exit_price: float,
                 pnl_pct: float, pnl_krw: float, exit_reason: str):
        self.entry_date = entry_date
        self.exit_date = exit_date
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.pnl_pct = pnl_pct
        self.pnl_krw = pnl_krw
        self.exit_reason = exit_reason

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}


def simulate(df: pd.DataFrame, initial_capital: float = 10_000_000.0) -> Tuple[List[Trade], pd.Series]:
    """일별 매매 시뮬레이션.

    Args:
        df: build_signal_df() 결과 DataFrame
        initial_capital: 초기 자본 (KRW)

    Returns:
        (trades, equity_series) — equity_series는 날별 총자산
    """
    rows = df.reset_index()  # date 컬럼화
    n = len(rows)

    capital = initial_capital
    position: Optional[Position] = None
    trades: List[Trade] = []
    equity: List[float] = []
    dates: List[Any] = []

    fee = RISK["fee"]
    sl = RISK["stop_loss"]
    tp = RISK["take_profit"]
    ptp_pct = RISK["partial_tp_pct"]
    ptp_ratio = RISK["partial_tp_ratio"]
    trail = RISK["trailing_stop"]
    trail_act = RISK["trailing_activate"]
    timecut = RISK["timecut_days"]
    inv_ratio = RISK["invest_ratio"]
    min_score = RISK["buy_composite_min"]

    for i, row in rows.iterrows():
        date_str = str(row["date"])[:10]
        price_o = float(row["open"])
        price_h = float(row["high"])
        price_l = float(row["low"])
        price_c = float(row["close"])
        composite = int(row.get("composite", 0))

        # 포지션 없을 때: 전날 스코어 ≥ 45 → 오늘 시가에 진입
        # (신호는 i-1일 발생, i일 시가에 진입)
        if position is None and i > 0:
            prev_score = int(rows.iloc[i - 1].get("composite", 0))
            if prev_score >= min_score and capital > 100_000:
                invest = capital * inv_ratio
                qty = invest * (1 - fee) / price_o
                capital -= invest
                position = Position(date_str, price_o, qty, invest)

        if position is not None:
            # 현재 수익률 (시가 기준 초기화)
            ret = (price_o - position.entry_price) / position.entry_price

            # 트레일링 활성화
            current_peak = max(position.peak_price, price_h)
            position.peak_price = current_peak
            if ret >= trail_act:
                position.trailing_active = True

            # ── 일중 SL/TP 체크 (저가→고가 순서로) ──

            exit_price: Optional[float] = None
            exit_reason: Optional[str] = None
            exit_qty = position.qty

            # 1. 손절 (저가 기준)
            sl_price = position.entry_price * (1 + sl)
            if price_l <= sl_price:
                exit_price = sl_price
                exit_reason = "SL"

            # 2. 익절 (고가 기준)
            if exit_price is None:
                tp_price = position.entry_price * (1 + tp)
                if price_h >= tp_price:
                    exit_price = tp_price
                    exit_reason = "TP"

            # 3. 부분익절 (고가 기준, 아직 안 했으면)
            if exit_price is None and not position.partial_done:
                ptp_price = position.entry_price * (1 + ptp_pct)
                if price_h >= ptp_price:
                    # 50% 매도
                    sold_qty = position.qty * ptp_ratio
                    proceeds = sold_qty * ptp_price * (1 - fee)
                    capital += proceeds
                    position.qty -= sold_qty
                    position.partial_done = True
                    # 부분익절만 하고 포지션 유지

            # 4. 트레일링 손절
            if exit_price is None and position.trailing_active:
                trail_sl = position.peak_price * (1 - trail)
                if price_l <= trail_sl:
                    exit_price = max(trail_sl, price_l)
                    exit_reason = "TRAILING"

            # 5. 시간 손절 (timecut_days 초과)
            if exit_price is None:
                held_days = (datetime.strptime(date_str, "%Y-%m-%d")
                             - datetime.strptime(position.entry_date, "%Y-%m-%d")).days
                if held_days >= timecut:
                    exit_price = price_c
                    exit_reason = "TIMECUT"

            # ── 포지션 종료 ──
            if exit_price is not None and exit_reason is not None:
                proceeds = exit_qty * exit_price * (1 - fee)
                capital += proceeds
                pnl_krw = proceeds - position.invested * (exit_qty / (position.qty + (position.invested * ptp_ratio / (position.entry_price * (1 + ptp_pct)) if position.partial_done else 0) + exit_qty))
                # 단순 PnL 계산
                pnl_pct = (exit_price / position.entry_price - 1) * 100
                trade = Trade(
                    entry_date=position.entry_date,
                    exit_date=date_str,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    pnl_pct=round(pnl_pct, 4),
                    pnl_krw=round(proceeds - position.invested, 0),
                    exit_reason=exit_reason,
                )
                trades.append(trade)
                position = None

        # 총자산 = 현금 + 포지션 평가액
        pos_val = position.qty * price_c if position else 0.0
        equity.append(capital + pos_val)
        dates.append(row["date"])

    equity_series = pd.Series(equity, index=pd.to_datetime(dates))
    return trades, equity_series


# ── 성과 지표 계산 ─────────────────────────────────────────────────────────────

def compute_metrics(
    trades: List[Trade],
    equity: pd.Series,
    initial_capital: float,
) -> Dict[str, Any]:
    """백테스트 성과 지표."""
    if equity.empty:
        return {}

    final = float(equity.iloc[-1])
    total_return_pct = (final / initial_capital - 1) * 100

    # 일별 수익률 → 샤프
    daily_ret = equity.pct_change().dropna()
    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std() * math.sqrt(252))
    else:
        sharpe = 0.0

    # MDD
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max * 100
    mdd = float(drawdown.min())

    # 거래 통계
    n_trades = len(trades)
    if n_trades == 0:
        return {
            "total_return_pct": round(total_return_pct, 2),
            "sharpe": round(sharpe, 3),
            "mdd_pct": round(mdd, 2),
            "n_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "monthly_returns": {},
        }

    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct < 0]
    win_rate = len(wins) / n_trades * 100

    avg_win = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0.0

    gross_profit = sum(t.pnl_pct for t in wins)
    gross_loss = abs(sum(t.pnl_pct for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # 월별 수익률
    monthly_ret: Dict[str, float] = {}
    monthly_eq = equity.resample("ME").last()
    monthly_eq_shifted = monthly_eq.shift(1)
    for dt, val in monthly_eq.items():
        prev = monthly_eq_shifted.get(dt, None)
        if prev and prev > 0:
            key = dt.strftime("%Y-%m")
            monthly_ret[key] = round((val / prev - 1) * 100, 2)

    # 최대 연속 손실
    max_consec_loss = 0
    cur_consec = 0
    for t in sorted(trades, key=lambda x: x.exit_date):
        if t.pnl_pct < 0:
            cur_consec += 1
            max_consec_loss = max(max_consec_loss, cur_consec)
        else:
            cur_consec = 0

    return {
        "total_return_pct": round(total_return_pct, 2),
        "sharpe": round(sharpe, 3),
        "mdd_pct": round(mdd, 2),
        "n_trades": n_trades,
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 3),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "max_consec_loss": max_consec_loss,
        "monthly_returns": monthly_ret,
    }


# ── 차트 생성 ──────────────────────────────────────────────────────────────────

_DARK_BG  = "#12141c"
_DARK_FG  = "#e0e2ec"
_DARK_GRID = "#2a2d3a"
_GREEN    = "#00c087"
_RED      = "#ff4d6d"
_BLUE     = "#4c9eff"
_YELLOW   = "#ffd166"


def save_chart(
    equity: pd.Series,
    bnh_equity: pd.Series,
    metrics: Dict[str, Any],
    output_path: Path,
) -> None:
    """수익곡선 + 드로다운 PNG 저장 (다크 테마)."""
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]}, facecolor=_DARK_BG
    )
    fig.patch.set_facecolor(_DARK_BG)

    # ── 수익 곡선 ─────────────────────────────────────
    ax1.set_facecolor(_DARK_BG)
    ax1.plot(equity.index, equity.values / equity.iloc[0] * 100 - 100,
             color=_GREEN, linewidth=1.8, label="전략 수익률", zorder=3)
    ax1.plot(bnh_equity.index, bnh_equity.values / bnh_equity.iloc[0] * 100 - 100,
             color=_BLUE, linewidth=1.2, linestyle="--", alpha=0.7,
             label="BTC 매수보유", zorder=2)
    ax1.axhline(0, color=_DARK_GRID, linewidth=0.8)
    ax1.set_ylabel("누적 수익률 (%)", color=_DARK_FG, fontsize=10)
    ax1.tick_params(colors=_DARK_FG, labelsize=9)
    ax1.spines[:].set_color(_DARK_GRID)
    ax1.set_facecolor(_DARK_BG)
    ax1.grid(True, color=_DARK_GRID, linewidth=0.5, alpha=0.5)
    ax1.legend(loc="upper left", facecolor="#1e2030", edgecolor=_DARK_GRID,
               labelcolor=_DARK_FG, fontsize=9)

    # 메트릭 텍스트
    stats_txt = (
        f"총수익률: {metrics.get('total_return_pct', 0):+.1f}%  "
        f"샤프: {metrics.get('sharpe', 0):.2f}  "
        f"MDD: {metrics.get('mdd_pct', 0):.1f}%  "
        f"승률: {metrics.get('win_rate', 0):.1f}%  "
        f"거래: {metrics.get('n_trades', 0)}건  "
        f"손익비: {metrics.get('profit_factor', 0):.2f}"
    )
    ax1.set_title(f"BTC 전략 백테스트\n{stats_txt}",
                  color=_DARK_FG, fontsize=10, pad=10)

    # ── 드로다운 ─────────────────────────────────────
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max * 100

    ax2.set_facecolor(_DARK_BG)
    ax2.fill_between(drawdown.index, drawdown.values, 0, color=_RED, alpha=0.6)
    ax2.plot(drawdown.index, drawdown.values, color=_RED, linewidth=0.8)
    ax2.set_ylabel("드로다운 (%)", color=_DARK_FG, fontsize=10)
    ax2.tick_params(colors=_DARK_FG, labelsize=9)
    ax2.spines[:].set_color(_DARK_GRID)
    ax2.grid(True, color=_DARK_GRID, linewidth=0.5, alpha=0.5)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right", color=_DARK_FG)

    plt.tight_layout(pad=1.5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)
    log.info(f"차트 저장: {output_path}")


# ── 메인 백테스트 클래스 ──────────────────────────────────────────────────────

class BacktestEngine:
    def __init__(
        self,
        days: int = 365,
        initial_capital: float = 10_000_000.0,
        output_dir: Optional[Path] = None,
    ):
        self.days = days
        self.initial_capital = initial_capital
        self.output_dir = output_dir or _DEFAULT_RESULTS_DIR

    def run(self, save: bool = True) -> Dict[str, Any]:
        log.info(f"백테스트 시작 — 기간: {self.days}일, 초기자본: ₩{self.initial_capital:,.0f}")

        # ── 1. 데이터 수집 ──
        df = load_ohlcv(self.days)
        fg_map = _fetch_fg_historical(limit=self.days + 50)

        # ── 2. 신호 계산 ──
        df = build_signal_df(df, fg_map)

        # 지표 초기화 기간(50일) 제거
        df = df.iloc[50:].copy()
        # 마지막 days행만 사용
        df = df.tail(self.days)

        if df.empty:
            log.warning("백테스트 데이터 없음")
            return {"ok": False, "error": "insufficient data"}

        # ── 3. 시뮬레이션 ──
        trades, equity = simulate(df, self.initial_capital)

        # BTC 매수보유 비교
        bnh = df["close"] / df["close"].iloc[0] * self.initial_capital
        bnh_series = pd.Series(bnh.values, index=equity.index if len(equity) == len(bnh) else bnh.index)

        # ── 4. 지표 계산 ──
        metrics = compute_metrics(trades, equity, self.initial_capital)

        # ── 5. 월별 수익률 테이블 출력 ──
        _print_monthly_table(metrics.get("monthly_returns", {}))

        # ── 6. 저장 ──
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "days": self.days,
            "initial_capital": self.initial_capital,
            "final_capital": round(float(equity.iloc[-1]) if not equity.empty else 0.0, 0),
            "metrics": metrics,
            "trades": [t.to_dict() for t in trades],
            "risk_params": RISK,
        }

        if save:
            json_path = self.output_dir / f"backtest_{timestamp}.json"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            log.info(f"JSON 저장: {json_path}")

            png_path = self.output_dir / f"backtest_{timestamp}.png"
            try:
                save_chart(equity, bnh_series, metrics, png_path)
            except Exception as e:
                log.warning(f"차트 저장 실패: {e}")

            result["json_path"] = str(json_path)
            result.setdefault("png_path", str(png_path))

        return result


def _print_monthly_table(monthly: Dict[str, float]) -> None:
    if not monthly:
        return
    print("\n── 월별 수익률 ──────────────────────────")
    for ym in sorted(monthly.keys()):
        val = monthly[ym]
        bar = "▲" if val >= 0 else "▼"
        color_open  = "\033[92m" if val >= 0 else "\033[91m"
        color_close = "\033[0m"
        print(f"  {ym}  {color_open}{bar} {val:+6.2f}%{color_close}")
    print("─────────────────────────────────────────")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli() -> int:
    parser = argparse.ArgumentParser(description="BTC 백테스트 엔진")
    parser.add_argument("--days", type=int, default=365, help="백테스트 기간 (일, 기본 365)")
    parser.add_argument("--capital", type=float, default=10_000_000, help="초기 자본 (KRW)")
    parser.add_argument("--no-save", action="store_true", help="결과 저장 생략")
    parser.add_argument("--output-dir", type=str, default=None, help="결과 저장 디렉터리")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None

    engine = BacktestEngine(
        days=args.days,
        initial_capital=args.capital,
        output_dir=output_dir,
    )
    result = engine.run(save=not args.no_save)

    m = result.get("metrics", {})
    print("\n══ 백테스트 결과 요약 ══════════════════════")
    print(f"  기간           : {result.get('days', '?')}일")
    print(f"  초기 자본      : ₩{result.get('initial_capital', 0):,.0f}")
    print(f"  최종 자본      : ₩{result.get('final_capital', 0):,.0f}")
    print(f"  총 수익률      : {m.get('total_return_pct', 0):+.2f}%")
    print(f"  연간 샤프 비율 : {m.get('sharpe', 0):.3f}")
    print(f"  최대 낙폭(MDD) : {m.get('mdd_pct', 0):.2f}%")
    print(f"  총 거래 횟수   : {m.get('n_trades', 0)}건")
    print(f"  승률           : {m.get('win_rate', 0):.2f}%")
    print(f"  손익비         : {m.get('profit_factor', 0):.3f}")
    print(f"  평균 수익 거래 : {m.get('avg_win_pct', 0):+.3f}%")
    print(f"  평균 손실 거래 : {m.get('avg_loss_pct', 0):+.3f}%")
    print(f"  최대 연속 손실 : {m.get('max_consec_loss', 0)}건")
    if result.get("json_path"):
        print(f"\n  JSON → {result['json_path']}")
    if result.get("png_path"):
        print(f"  PNG  → {result['png_path']}")
    print("═══════════════════════════════════════════")

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
