"""KR 주식 전용 백테스트 파이프라인 (Phase 4-2).

복합 스코어(100점) — RSI·MACD·BB·거래량·모멘텀 5개 팩터
진입: score >= 65, 청산: score <= 40
손절 -5%, 익절 +10%
포지션 사이징: Kelly 50% + max_single 3%

실행 예시:
    python -m quant.backtest_kr --start 2025-04-21 --end 2026-04-20 --universe top10
    python -m quant.backtest_kr --start 2026-03-01 --end 2026-04-01 --universe 005930,000660
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 프로젝트 루트 sys.path 주입 ────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("backtest_kr")

# ── 시가총액 상위 10종목 (stock_data_collector.TOP_STOCKS 기준) ─────────────
TOP10_UNIVERSE: List[Dict[str, str]] = [
    {"code": "005930", "name": "삼성전자"},
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "373220", "name": "LG에너지솔루션"},
    {"code": "207940", "name": "삼성바이오로직스"},
    {"code": "005380", "name": "현대차"},
    {"code": "006400", "name": "삼성SDI"},
    {"code": "051910", "name": "LG화학"},
    {"code": "035420", "name": "NAVER"},
    {"code": "000270", "name": "기아"},
    {"code": "068270", "name": "셀트리온"},
]

# ── 기본 파라미터 ──────────────────────────────────────────────────────────────
DEFAULT_ENTRY_SCORE = 65
DEFAULT_EXIT_SCORE = 40
STOP_LOSS = -0.05      # -5%
TAKE_PROFIT = 0.10     # +10%
FEE_RATE = 0.0015      # 매수/매도 각 0.15%
KELLY_FRACTION = 0.50  # Kelly 50%
MAX_SINGLE_RATIO = 0.03  # 단일 종목 최대 3%
RESULTS_DIR = Path(__file__).resolve().parent / "backtest" / "results"


# ── Pure-math helpers ──────────────────────────────────────────────────────────

def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


# ── 기술 지표 계산 (pure-python, ta 의존 없음) ────────────────────────────────

def _calc_rsi(closes: List[float], window: int = 14) -> float:
    if len(closes) < window + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, window + 1):
        delta = closes[-window - 1 + i] - closes[-window - 1 + i - 1]
        (gains if delta > 0 else losses).append(abs(delta))
    avg_gain = _mean(gains) if gains else 0.0
    avg_loss = _mean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _calc_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float]:
    """MACD 라인, 시그널 라인 반환."""
    if len(closes) < slow + signal:
        return 0.0, 0.0

    def _ema(data: List[float], period: int) -> List[float]:
        k = 2.0 / (period + 1)
        result = [data[0]]
        for p in data[1:]:
            result.append(p * k + result[-1] * (1 - k))
        return result

    ema_fast = _ema(closes[-(slow + signal + 10):], fast)
    ema_slow = _ema(closes[-(slow + signal + 10):], slow)
    min_len = min(len(ema_fast), len(ema_slow))
    macd_line = [ema_fast[-min_len + i] - ema_slow[-min_len + i] for i in range(min_len)]
    if len(macd_line) < signal:
        return macd_line[-1] if macd_line else 0.0, 0.0
    signal_line = _ema(macd_line[-signal - 5:], signal)
    return macd_line[-1], signal_line[-1]


def _calc_bb_pos(closes: List[float], window: int = 20) -> float:
    """볼린저밴드 내 위치 (0~100%). 하단=0, 중앙=50, 상단=100."""
    if len(closes) < window:
        return 50.0
    recent = closes[-window:]
    mid = _mean(recent)
    std = _std(recent)
    if std == 0:
        return 50.0
    upper = mid + 2 * std
    lower = mid - 2 * std
    pos = (closes[-1] - lower) / (upper - lower) * 100.0
    return max(0.0, min(100.0, pos))


def _calc_vol_ratio(volumes: List[float], window: int = 20) -> float:
    if len(volumes) < window + 1:
        return 1.0
    avg = _mean(volumes[-window - 1:-1])
    return volumes[-1] / avg if avg > 0 else 1.0


def _calc_momentum(closes: List[float]) -> float:
    """5일·20일 수익률 기반 모멘텀 점수 (0~100)."""
    if len(closes) < 21:
        return 50.0
    ret_5 = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else 0.0
    ret_20 = (closes[-1] / closes[-21] - 1) * 100 if len(closes) >= 21 else 0.0
    raw = ret_5 * 0.6 + ret_20 * 0.4
    return max(0.0, min(100.0, 50.0 + raw * 5.0))


# ── 복합 스코어 (100점) ────────────────────────────────────────────────────────

def calc_composite_score(closes: List[float], volumes: List[float]) -> float:
    """RSI·MACD·BB·거래량·모멘텀 5팩터 복합 스코어 (0~100).

    배점:
        RSI        20점
        MACD       20점
        BB         20점
        거래량     20점
        모멘텀     20점
    """
    if len(closes) < 30 or len(volumes) < 21:
        return 0.0

    score = 0.0

    # 1) RSI (20점)
    rsi = _calc_rsi(closes, window=14)
    if rsi <= 30:
        score += 20
    elif rsi <= 40:
        score += 15
    elif rsi <= 50:
        score += 10
    elif rsi >= 70:
        score += 0   # 과매수
    else:
        score += 5

    # 2) MACD (20점)
    macd_val, macd_sig = _calc_macd(closes)
    macd_hist = macd_val - macd_sig
    if macd_val > 0 and macd_hist > 0:
        score += 20
    elif macd_val > 0 or macd_hist > 0:
        score += 12
    elif macd_val < 0 and macd_hist < 0:
        score += 0
    else:
        score += 5

    # 3) BB 위치 (20점)
    bb_pos = _calc_bb_pos(closes, window=20)
    if bb_pos <= 20:
        score += 20
    elif bb_pos <= 35:
        score += 14
    elif bb_pos <= 50:
        score += 8
    elif bb_pos >= 80:
        score += 0
    else:
        score += 3

    # 4) 거래량 (20점)
    vol_ratio = _calc_vol_ratio(volumes, window=20)
    if vol_ratio >= 2.0:
        score += 20
    elif vol_ratio >= 1.5:
        score += 15
    elif vol_ratio >= 1.2:
        score += 10
    elif vol_ratio >= 0.8:
        score += 5
    else:
        score += 0

    # 5) 모멘텀 (20점)
    mom = _calc_momentum(closes)
    if mom >= 75:
        score += 20
    elif mom >= 60:
        score += 15
    elif mom >= 50:
        score += 10
    elif mom >= 40:
        score += 5
    else:
        score += 0

    return round(score, 2)


# ── 데이터 로드 ────────────────────────────────────────────────────────────────

def _load_ohlcv_pykrx(code: str, start: str, end: str) -> List[dict]:
    """pykrx로 일봉 OHLCV 로드. YYYYMMDD 형식 입력."""
    try:
        from pykrx import stock as pykrx_stock
        start_fmt = start.replace("-", "")
        end_fmt = end.replace("-", "")
        df = pykrx_stock.get_market_ohlcv_by_date(start_fmt, end_fmt, code)
        if df is None or df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            rows.append({
                "date": str(idx.date()) if hasattr(idx, "date") else str(idx)[:10],
                "open": _safe_float(row.get("시가") or row.get("Open")),
                "high": _safe_float(row.get("고가") or row.get("High")),
                "low": _safe_float(row.get("저가") or row.get("Low")),
                "close": _safe_float(row.get("종가") or row.get("Close")),
                "volume": _safe_float(row.get("거래량") or row.get("Volume")),
            })
        return rows
    except Exception as exc:
        log.warning("pykrx OHLCV 로드 실패", code=code, error=str(exc))
        return []


def _load_ohlcv_supabase(code: str, start: str, end: str) -> List[dict]:
    """Supabase daily_ohlcv 테이블 fallback."""
    try:
        from common.supabase_client import get_supabase
        sb = get_supabase()
        if not sb:
            return []
        rows = (
            sb.table("daily_ohlcv")
            .select("date,open_price,high_price,low_price,close_price,volume")
            .eq("stock_code", code)
            .gte("date", start)
            .lte("date", end)
            .order("date", desc=False)
            .execute()
            .data
            or []
        )
        out = []
        for r in rows:
            out.append({
                "date": str(r.get("date") or "")[:10],
                "open": _safe_float(r.get("open_price")),
                "high": _safe_float(r.get("high_price")),
                "low": _safe_float(r.get("low_price")),
                "close": _safe_float(r.get("close_price")),
                "volume": _safe_float(r.get("volume")),
            })
        return out
    except Exception as exc:
        log.warning("Supabase OHLCV 로드 실패", code=code, error=str(exc))
        return []


def load_ohlcv(code: str, start: str, end: str) -> List[dict]:
    """pykrx 우선, 실패 시 Supabase fallback. 둘 다 실패 시 빈 리스트."""
    # 지표 계산용 warm-up 기간 확보 (60일 앞당겨 로드)
    start_dt = datetime.strptime(start, "%Y-%m-%d") - timedelta(days=90)
    start_ext = start_dt.strftime("%Y-%m-%d")

    rows = _load_ohlcv_pykrx(code, start_ext, end)
    if not rows:
        log.info("pykrx 데이터 없음 → Supabase fallback", code=code)
        rows = _load_ohlcv_supabase(code, start_ext, end)
    if not rows:
        log.warning("OHLCV 데이터 없음 (pykrx + Supabase 모두 실패)", code=code)
    return rows


# ── 유니버스 해석 ──────────────────────────────────────────────────────────────

def resolve_universe(universe_arg: str) -> List[str]:
    """'top10' 또는 '005930,000660,...' 형태 파싱 → 종목 코드 리스트."""
    if universe_arg.strip().lower() == "top10":
        return [s["code"] for s in TOP10_UNIVERSE]
    codes = [c.strip() for c in universe_arg.split(",") if c.strip()]
    return codes


# ── Kelly 포지션 사이징 ────────────────────────────────────────────────────────

def kelly_size(capital: float, win_rate: float = 0.56, avg_win: float = 0.10, avg_loss: float = 0.05) -> float:
    """Kelly 50% 적용 + max_single 3% 상한."""
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1.0 - win_rate
    kelly_full = (b * win_rate - q) / b
    kelly_half = max(0.0, kelly_full * KELLY_FRACTION)
    capped = min(kelly_half, MAX_SINGLE_RATIO)
    return capital * capped


# ── 백테스트 메인 엔진 ────────────────────────────────────────────────────────

def run_backtest(
    codes: List[str],
    start: str,
    end: str,
    initial_capital: float = 10_000_000.0,
    entry_score: float = DEFAULT_ENTRY_SCORE,
    exit_score: float = DEFAULT_EXIT_SCORE,
) -> dict:
    """단일 종목 순환 백테스트 (미보유 종목 매일 스캔 → 시그널 발생 시 진입).

    Returns
    -------
    dict — 요약 메트릭 + 거래 내역
    """
    # 1) 데이터 로드
    log.info("OHLCV 데이터 로드 중...", n_codes=len(codes))
    series: Dict[str, List[dict]] = {}
    for code in codes:
        rows = load_ohlcv(code, start, end)
        if rows:
            series[code] = rows
        else:
            log.warning("데이터 없음 → 유니버스에서 제외", code=code)

    if not series:
        log.error("유효한 데이터 없음 — 백테스트 중단")
        return {"error": "no data available", "trades": [], "metrics": {}}

    # 2) 거래일 달력 구성 (모든 종목의 날짜 합집합)
    all_dates: set = set()
    for rows in series.values():
        for r in rows:
            d = r["date"]
            if start <= d <= end:
                all_dates.add(d)
    calendar = sorted(all_dates)

    if len(calendar) < 10:
        log.warning("거래일 부족", n_days=len(calendar))
        return {"error": f"too few trading days: {len(calendar)}", "trades": [], "metrics": {}}

    # 3) 포트폴리오 시뮬레이션
    capital = float(initial_capital)
    # positions: code → {entry_price, shares, entry_date, entry_score}
    positions: Dict[str, dict] = {}
    trades: List[dict] = []
    equity_curve: List[float] = [capital]

    # 과거 승률/평균손익 추정 (Kelly 계산용 초기값)
    _win_hist: List[float] = []

    for today in calendar:
        # ── 기존 포지션 청산 체크 ──
        to_close: List[str] = []
        for code, pos in positions.items():
            rows = series[code]
            # 오늘 종가 조회
            today_row = next((r for r in rows if r["date"] == today), None)
            if today_row is None:
                continue
            price = _safe_float(today_row["close"])
            if price <= 0:
                continue

            pnl_gross = (price - pos["entry_price"]) / pos["entry_price"]
            pnl_net = pnl_gross - FEE_RATE * 2  # 매수 + 매도 수수료

            # 손절/익절 먼저
            exit_reason = None
            if pnl_net <= STOP_LOSS:
                exit_reason = "stop_loss"
            elif pnl_net >= TAKE_PROFIT:
                exit_reason = "take_profit"
            else:
                # 스코어 청산 확인
                closes = [_safe_float(r["close"]) for r in rows if r["date"] <= today and _safe_float(r["close"]) > 0]
                vols = [_safe_float(r["volume"]) for r in rows if r["date"] <= today and _safe_float(r["volume"]) >= 0]
                if len(closes) >= 30 and len(vols) >= 21:
                    curr_score = calc_composite_score(closes, vols)
                    if curr_score <= exit_score:
                        exit_reason = "score_exit"

            if exit_reason:
                proceeds = pos["shares"] * price * (1 - FEE_RATE)
                capital += proceeds
                hold_days = (
                    datetime.strptime(today, "%Y-%m-%d")
                    - datetime.strptime(pos["entry_date"], "%Y-%m-%d")
                ).days
                trades.append({
                    "code": code,
                    "entry": pos["entry_date"],
                    "exit": today,
                    "entry_price": round(pos["entry_price"], 2),
                    "exit_price": round(price, 2),
                    "pnl_pct": round(pnl_net * 100, 2),
                    "days": hold_days,
                    "reason": exit_reason,
                })
                _win_hist.append(pnl_net)
                to_close.append(code)

        for code in to_close:
            del positions[code]

        # ── 신규 진입 스캔 ──
        for code in codes:
            if code in positions:
                continue
            rows = series.get(code)
            if not rows:
                continue
            today_row = next((r for r in rows if r["date"] == today), None)
            if today_row is None:
                continue
            price = _safe_float(today_row["close"])
            if price <= 0:
                continue

            # 오늘까지의 히스토리 슬라이스
            hist_rows = [r for r in rows if r["date"] <= today]
            closes = [_safe_float(r["close"]) for r in hist_rows if _safe_float(r["close"]) > 0]
            vols = [_safe_float(r["volume"]) for r in hist_rows if _safe_float(r["volume"]) >= 0]

            if len(closes) < 30 or len(vols) < 21:
                continue

            curr_score = calc_composite_score(closes, vols)
            if curr_score < entry_score:
                continue

            # Kelly 사이징
            if _win_hist:
                wins = [p for p in _win_hist if p > 0]
                losses = [abs(p) for p in _win_hist if p < 0]
                wr = len(wins) / len(_win_hist)
                aw = _mean(wins) if wins else TAKE_PROFIT
                al = _mean(losses) if losses else abs(STOP_LOSS)
            else:
                wr, aw, al = 0.56, TAKE_PROFIT, abs(STOP_LOSS)

            invest = kelly_size(capital, win_rate=wr, avg_win=aw, avg_loss=al)
            if invest < 10_000:  # 최소 1만원
                continue
            if invest > capital:
                invest = capital * MAX_SINGLE_RATIO

            cost = invest * (1 + FEE_RATE)
            if cost > capital:
                continue

            shares = invest / price
            capital -= cost
            positions[code] = {
                "entry_price": price,
                "shares": shares,
                "entry_date": today,
                "entry_score": curr_score,
            }
            log.debug("진입", code=code, date=today, score=curr_score, invest=round(invest))

        # 당일 포트폴리오 평가액
        pos_value = sum(
            pos["shares"] * _safe_float(
                next((r["close"] for r in series.get(c, []) if r["date"] == today), 0) or 0
            )
            for c, pos in positions.items()
        )
        equity_curve.append(capital + pos_value)

    # ── 미청산 포지션 마감 (마지막 날 종가) ──
    last_date = calendar[-1] if calendar else end
    for code, pos in positions.items():
        rows = series.get(code, [])
        last_row = next((r for r in reversed(rows) if r["date"] <= last_date), None)
        if last_row is None:
            continue
        price = _safe_float(last_row["close"])
        if price <= 0:
            continue
        pnl_net = (price - pos["entry_price"]) / pos["entry_price"] - FEE_RATE * 2
        proceeds = pos["shares"] * price * (1 - FEE_RATE)
        capital += proceeds
        hold_days = (
            datetime.strptime(last_date, "%Y-%m-%d")
            - datetime.strptime(pos["entry_date"], "%Y-%m-%d")
        ).days
        trades.append({
            "code": code,
            "entry": pos["entry_date"],
            "exit": last_date,
            "entry_price": round(pos["entry_price"], 2),
            "exit_price": round(price, 2),
            "pnl_pct": round(pnl_net * 100, 2),
            "days": hold_days,
            "reason": "forced_close",
        })

    # ── 메트릭 계산 ──
    metrics = _calc_metrics(initial_capital, capital, equity_curve, trades)

    return {
        "period": {"start": start, "end": end},
        "universe": codes,
        "trades": trades,
        "metrics": metrics,
    }


def _calc_metrics(
    initial: float,
    final: float,
    equity_curve: List[float],
    trades: List[dict],
) -> dict:
    total_return = (final - initial) / initial if initial > 0 else 0.0

    # 일별 수익률
    daily_rets = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        curr = equity_curve[i]
        daily_rets.append((curr - prev) / prev if prev > 0 else 0.0)

    # Sharpe (연환산, 무위험이자율 0)
    sharpe = 0.0
    if len(daily_rets) >= 2:
        std = _std(daily_rets)
        if std > 0:
            sharpe = _mean(daily_rets) / std * math.sqrt(252)

    # Max Drawdown
    max_dd = 0.0
    peak = equity_curve[0] if equity_curve else initial
    for val in equity_curve:
        peak = max(peak, val)
        if peak > 0:
            dd = (peak - val) / peak
            max_dd = max(max_dd, dd)

    # Win rate / avg holding
    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]
    win_rate = len(wins) / len(pnls) if pnls else 0.0
    avg_hold = _mean([t.get("days", 0) for t in trades]) if trades else 0.0

    return {
        "total_return": round(total_return, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(-max_dd, 4),
        "win_rate": round(win_rate, 4),
        "n_trades": len(trades),
        "avg_holding_days": round(avg_hold, 2),
        "initial_capital": initial,
        "final_capital": round(final, 0),
    }


# ── 결과 저장 ──────────────────────────────────────────────────────────────────

def save_result(result: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"kr_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return out_path


# ── 요약 테이블 출력 ───────────────────────────────────────────────────────────

def print_summary(result: dict, out_path: Optional[Path] = None) -> None:
    m = result.get("metrics", {})
    trades = result.get("trades", [])
    period = result.get("period", {})

    print("=" * 58)
    print("  KR 백테스트 결과")
    print(f"  기간: {period.get('start')} ~ {period.get('end')}")
    print(f"  유니버스: {', '.join(result.get('universe', []))}")
    print("=" * 58)
    print(f"  총 수익률    : {m.get('total_return', 0) * 100:+.2f}%")
    print(f"  Sharpe       : {m.get('sharpe', 0):.3f}")
    print(f"  Max Drawdown : {m.get('max_drawdown', 0) * 100:.2f}%")
    print(f"  승률         : {m.get('win_rate', 0) * 100:.1f}%")
    print(f"  거래 횟수    : {m.get('n_trades', 0)}")
    print(f"  평균 보유일  : {m.get('avg_holding_days', 0):.1f}일")
    print(f"  초기 자본    : {m.get('initial_capital', 0):,.0f}원")
    print(f"  최종 자본    : {m.get('final_capital', 0):,.0f}원")
    print("-" * 58)
    if trades:
        print(f"  {'종목':<8} {'진입일':<12} {'청산일':<12} {'수익률':>8} {'보유일':>6} {'사유'}")
        print(f"  {'-'*7} {'-'*11} {'-'*11} {'-'*8} {'-'*6} {'-'*10}")
        for t in trades[-20:]:  # 최근 20건만 출력
            print(
                f"  {t['code']:<8} {t['entry']:<12} {t['exit']:<12}"
                f" {t['pnl_pct']:>+7.2f}% {t['days']:>6} {t.get('reason', '')}"
            )
    if out_path:
        print(f"\n  결과 저장: {out_path}")
    print("=" * 58)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli() -> int:
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    parser = argparse.ArgumentParser(description="KR 주식 백테스트")
    parser.add_argument("--start", default=one_year_ago.isoformat(), help="시작일 YYYY-MM-DD")
    parser.add_argument("--end", default=today.isoformat(), help="종료일 YYYY-MM-DD")
    parser.add_argument(
        "--universe",
        default="top10",
        help="'top10' 또는 종목 코드 CSV (예: 005930,000660)",
    )
    parser.add_argument("--initial-capital", type=float, default=10_000_000.0, help="초기 자본 (KRW)")
    parser.add_argument("--entry-score", type=float, default=DEFAULT_ENTRY_SCORE, help="진입 스코어 임계값")
    parser.add_argument("--exit-score", type=float, default=DEFAULT_EXIT_SCORE, help="청산 스코어 임계값")
    parser.add_argument("--no-save", action="store_true", help="결과 JSON 저장 안 함")
    args = parser.parse_args()

    codes = resolve_universe(args.universe)
    if not codes:
        print("[ERROR] 유니버스가 비어 있음", file=sys.stderr)
        return 2

    log.info(
        "백테스트 시작",
        start=args.start,
        end=args.end,
        universe=codes,
        capital=args.initial_capital,
        entry_score=args.entry_score,
        exit_score=args.exit_score,
    )

    result = run_backtest(
        codes=codes,
        start=args.start,
        end=args.end,
        initial_capital=args.initial_capital,
        entry_score=args.entry_score,
        exit_score=args.exit_score,
    )

    if result.get("error"):
        print(f"[ERROR] {result['error']}", file=sys.stderr)
        return 1

    out_path = None
    if not args.no_save:
        out_path = save_result(result)

    print_summary(result, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
