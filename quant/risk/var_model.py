"""Portfolio VaR/CVaR model for Phase 11.

Core outputs:
{ var_95, var_99, cvar_95, portfolio_vol, diversification_ratio }
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Dict, Iterable, List, Mapping, Sequence

from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("risk_var")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _std(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (n - 1)
    return float(math.sqrt(var))


def _percentile(values: Sequence[float], q: float) -> float:
    """q in [0, 100]. Linear interpolation percentile."""
    if not values:
        return 0.0
    arr = sorted(float(v) for v in values)
    n = len(arr)
    if n == 1:
        return arr[0]
    q = max(0.0, min(100.0, q))
    pos = (q / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return arr[lo]
    w = pos - lo
    return arr[lo] * (1.0 - w) + arr[hi] * w


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _coerce_returns_matrix(returns_matrix) -> Dict[str, List[float]]:
    """Accept dict-like or pandas.DataFrame and return symbol->return series."""
    if returns_matrix is None:
        return {}

    if hasattr(returns_matrix, "to_dict"):
        try:
            # DataFrame columns -> list
            cols = list(getattr(returns_matrix, "columns", []))
            out = {}
            for c in cols:
                series = returns_matrix[c]
                out[_normalize_symbol(c)] = [
                    _safe_float(v) for v in list(series) if isinstance(_safe_float(v, None), float)
                ]
            if out:
                return out
        except Exception:
            pass

    if isinstance(returns_matrix, Mapping):
        out = {}
        for k, vals in returns_matrix.items():
            if not isinstance(vals, Iterable):
                continue
            out[_normalize_symbol(k)] = [_safe_float(v) for v in vals]
        return out

    return {}


def _extract_weights(positions: List[dict], symbols: List[str]) -> Dict[str, float]:
    symbol_set = set(symbols)
    raw: Dict[str, float] = {}
    for p in positions:
        sym = _normalize_symbol(p.get("symbol") or p.get("ticker") or p.get("code"))
        if not sym or sym not in symbol_set:
            continue

        # priority: explicit weight -> market_value/value/notional -> quantity*price
        w = _safe_float(p.get("weight"), 0.0)
        if w <= 0:
            mv = _safe_float(
                p.get("market_value")
                or p.get("value")
                or p.get("notional")
                or p.get("exposure"),
                0.0,
            )
            if mv > 0:
                w = mv
            else:
                qty = _safe_float(p.get("quantity") or p.get("qty"), 0.0)
                px = _safe_float(p.get("price") or p.get("entry_price") or p.get("current_price"), 0.0)
                w = qty * px

        if w > 0:
            raw[sym] = raw.get(sym, 0.0) + w

    if not raw:
        # equal-weight fallback
        n = len(symbols)
        return {s: (1.0 / n if n > 0 else 0.0) for s in symbols}

    total = sum(raw.values())
    if total <= 0:
        n = len(symbols)
        return {s: (1.0 / n if n > 0 else 0.0) for s in symbols}
    return {s: raw.get(s, 0.0) / total for s in symbols}


def _align_series(matrix: Dict[str, List[float]], symbols: List[str], lookback: int = 252) -> Dict[str, List[float]]:
    lengths = [len(matrix.get(s) or []) for s in symbols if matrix.get(s)]
    if not lengths:
        return {}
    n = min(min(lengths), max(lookback, 2))
    out = {}
    for s in symbols:
        vals = matrix.get(s) or []
        if len(vals) < n:
            continue
        out[s] = [float(v) for v in vals[-n:]]
    return out


def _portfolio_return_series(aligned: Dict[str, List[float]], weights: Dict[str, float]) -> List[float]:
    symbols = [s for s in aligned.keys() if s in weights]
    if not symbols:
        return []
    n = min(len(aligned[s]) for s in symbols)
    if n <= 0:
        return []
    out = []
    for i in range(n):
        r = 0.0
        for s in symbols:
            r += weights.get(s, 0.0) * aligned[s][i]
        out.append(float(r))
    return out


def _historical_var_cvar(portfolio_returns: Sequence[float], confidence: float) -> tuple[float, float]:
    if not portfolio_returns:
        return 0.0, 0.0
    alpha = max(0.0, min(1.0, confidence))
    tail_q = (1.0 - alpha) * 100.0
    q = _percentile(portfolio_returns, tail_q)
    var = max(0.0, -q)
    tails = [r for r in portfolio_returns if r <= q]
    cvar = max(0.0, -_mean(tails)) if tails else var
    return float(var), float(cvar)


def _parametric_var(portfolio_returns: Sequence[float], confidence: float) -> float:
    if len(portfolio_returns) < 2:
        return 0.0
    mu = _mean(portfolio_returns)
    sigma = _std(portfolio_returns)
    if sigma <= 0:
        return 0.0
    z_tail = NormalDist().inv_cdf(max(1e-6, 1.0 - confidence))
    # quantile in return space, convert to positive loss
    q = mu + z_tail * sigma
    return max(0.0, -q)


def _diversification_ratio(aligned: Dict[str, List[float]], weights: Dict[str, float], portfolio_vol: float) -> float:
    if portfolio_vol <= 0:
        return 1.0
    agg = 0.0
    for sym, vals in aligned.items():
        agg += weights.get(sym, 0.0) * _std(vals)
    if agg <= 0:
        return 1.0
    return agg / portfolio_vol


def compute_var_metrics(
    positions: List[dict],
    returns_matrix,
    lookback_days: int = 252,
) -> dict:
    """Compute historical/parametric VaR and CVaR from positions + returns matrix."""
    matrix = _coerce_returns_matrix(returns_matrix)
    if not matrix:
        return {
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "portfolio_vol": 0.0,
            "diversification_ratio": 1.0,
        }

    symbols = sorted({_normalize_symbol(p.get("symbol") or p.get("ticker") or p.get("code")) for p in positions})
    symbols = [s for s in symbols if s and s in matrix]
    if not symbols:
        symbols = sorted(matrix.keys())

    aligned = _align_series(matrix, symbols=symbols, lookback=lookback_days)
    if not aligned:
        return {
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "portfolio_vol": 0.0,
            "diversification_ratio": 1.0,
        }

    weights = _extract_weights(positions, symbols=list(aligned.keys()))
    port = _portfolio_return_series(aligned, weights)
    if len(port) < 2:
        return {
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "portfolio_vol": 0.0,
            "diversification_ratio": 1.0,
        }

    var_95, cvar_95 = _historical_var_cvar(port, confidence=0.95)
    var_99, _ = _historical_var_cvar(port, confidence=0.99)
    pvar_95 = _parametric_var(port, confidence=0.95)
    pvar_99 = _parametric_var(port, confidence=0.99)
    port_vol = _std(port)
    div_ratio = _diversification_ratio(aligned, weights, portfolio_vol=port_vol)

    return {
        "var_95": round(var_95, 6),
        "var_99": round(var_99, 6),
        "cvar_95": round(cvar_95, 6),
        "portfolio_vol": round(port_vol, 6),
        "diversification_ratio": round(div_ratio, 6),
        "parametric_var_95": round(pvar_95, 6),
        "parametric_var_99": round(pvar_99, 6),
        "sample_days": len(port),
        "symbols": sorted(aligned.keys()),
    }


class VaRModel:
    """Convenience wrapper for VaR/CVaR calculations."""

    def __init__(self, lookback_days: int = 252):
        self.lookback_days = max(lookback_days, 30)

    def compute(self, positions: List[dict], returns_matrix) -> dict:
        return compute_var_metrics(
            positions=positions,
            returns_matrix=returns_matrix,
            lookback_days=self.lookback_days,
        )


def fetch_return_matrix(symbols: List[str], lookback_days: int = 252) -> Dict[str, List[float]]:
    """Fetch simple daily return matrix from yfinance for standalone runs."""
    out: Dict[str, List[float]] = {}
    uniq = sorted({_normalize_symbol(s) for s in symbols if _normalize_symbol(s)})
    if not uniq:
        return out

    try:
        import yfinance as yf

        for sym in uniq:
            hist = retry_call(
                yf.Ticker(sym).history,
                kwargs={"period": f"{lookback_days + 30}d", "interval": "1d"},
                max_attempts=2,
                base_delay=1.0,
                default=None,
            )
            if hist is None or hist.empty or "Close" not in hist:
                continue
            close = [float(v) for v in list(hist["Close"]) if _safe_float(v, 0.0) > 0]
            if len(close) < 3:
                continue
            rets = []
            for i in range(1, len(close)):
                prev = close[i - 1]
                cur = close[i]
                if prev > 0:
                    rets.append(cur / prev - 1.0)
            if rets:
                out[sym] = rets[-lookback_days:]
    except Exception as exc:
        log.warn("fetch_return_matrix failed", error=exc)

    return out


if __name__ == "__main__":
    sample_positions = [
        {"symbol": "AAPL", "market_value": 30000},
        {"symbol": "MSFT", "market_value": 25000},
        {"symbol": "NVDA", "market_value": 20000},
    ]
    matrix = fetch_return_matrix([p["symbol"] for p in sample_positions], lookback_days=252)
    if not matrix:
        matrix = {
            "AAPL": [0.002, -0.004, 0.001, -0.007, 0.003] * 60,
            "MSFT": [0.001, -0.003, 0.002, -0.006, 0.002] * 60,
            "NVDA": [0.004, -0.009, 0.003, -0.012, 0.005] * 60,
        }
    result = compute_var_metrics(sample_positions, matrix)
    log.info("var_metrics", **result)
