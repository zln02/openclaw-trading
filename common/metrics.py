"""공통 PnL 계산 유틸리티 — OpenClaw Trading System.

사용법:
    from common.metrics import calc_trade_pnl, calc_win_rate, calc_sharpe
"""
from __future__ import annotations

from typing import Optional


def calc_trade_pnl(trade: dict, *, market: str = "kr") -> Optional[float]:
    """거래 PnL% 계산 (통합 함수).

    지원 스키마 (우선순위 순):
    1. pnl_pct (직접 저장된 %)
    2. pnl (절대값) + entry_price / buy_price
    3. exit_price + entry_price (US 스키마)
    4. price + entry_price (KR 매도 스키마)

    Args:
        trade: 거래 레코드 dict
        market: 'btc' | 'kr' | 'us' (미사용이나 향후 확장용)

    Returns:
        float: PnL 퍼센트 (예: 2.5 = +2.5%, -3.0 = -3%), None if 계산 불가
    """
    # 1. pnl_pct 직접 사용
    v = trade.get("pnl_pct")
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass

    # 2. pnl 절대값 → % 변환
    pnl_abs = trade.get("pnl")
    if pnl_abs is not None:
        entry = _first_valid(trade, "entry_price", "buy_price", "price")
        if entry is not None and entry > 0:
            try:
                return float(pnl_abs) / entry * 100
            except (TypeError, ValueError, ZeroDivisionError):
                pass

    # 3. exit_price + entry_price
    exit_p = _first_valid(trade, "exit_price")
    entry_p = _first_valid(trade, "entry_price", "buy_price")
    if exit_p is not None and entry_p is not None and entry_p > 0:
        try:
            return (exit_p - entry_p) / entry_p * 100
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    # 4. price (매도가) + entry_price
    sell_p = _first_valid(trade, "price")
    entry_p2 = _first_valid(trade, "entry_price", "buy_price")
    if sell_p is not None and entry_p2 is not None and entry_p2 > 0:
        try:
            return (sell_p - entry_p2) / entry_p2 * 100
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    return None


def _first_valid(trade: dict, *keys: str) -> Optional[float]:
    """여러 키 중 첫 번째 유효한 float 반환."""
    for k in keys:
        v = trade.get(k)
        if v is not None:
            try:
                f = float(v)
                if f != 0:
                    return f
            except (TypeError, ValueError):
                pass
    return None


def calc_win_rate(trades: list, *, market: str = "kr") -> float:
    """승률 계산.

    Args:
        trades: 거래 레코드 리스트
        market: 시장 구분

    Returns:
        float: 승률 (0.0 ~ 1.0)
    """
    pnls = [calc_trade_pnl(t, market=market) for t in trades]
    valid = [p for p in pnls if p is not None]
    if not valid:
        return 0.0
    wins = sum(1 for p in valid if p > 0)
    return wins / len(valid)


def calc_sharpe(pnl_series: list, *, annualize: int = 252) -> float:
    """샤프 비율 계산.

    Args:
        pnl_series: 기간별 수익률 리스트 (%)
        annualize: 연환산 계수 (일간=252, 주간=52)

    Returns:
        float: 샤프 비율
    """
    try:
        import numpy as np
        arr = np.array(pnl_series, dtype=float)
        if len(arr) < 2:
            return 0.0
        std = arr.std()
        if std == 0:
            return 0.0
        return float(arr.mean() / std * (annualize ** 0.5))
    except Exception:
        return 0.0


def calc_max_drawdown(equity_curve: list) -> float:
    """최대 낙폭(MDD) 계산.

    Args:
        equity_curve: 자산 곡선 리스트 (순서대로)

    Returns:
        float: MDD % (예: -15.3)
    """
    try:
        import numpy as np
        arr = np.array(equity_curve, dtype=float)
        if len(arr) < 2:
            return 0.0
        peak = arr.cummax() if hasattr(arr, 'cummax') else None
        if peak is None:
            # numpy로 직접 계산
            running_max = np.maximum.accumulate(arr)
            drawdowns = (arr - running_max) / np.where(running_max != 0, running_max, 1)
            return float(drawdowns.min() * 100)
        return 0.0
    except Exception:
        return 0.0
