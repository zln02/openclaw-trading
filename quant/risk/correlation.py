"""Rolling correlation monitor for Phase 11.

Features:
- 60-day rolling correlation matrix
- pairwise alert when correlation > threshold (default 0.7)
- spike detection vs previous snapshot
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Sequence

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import send_telegram
from quant.risk.var_model import _safe_float, fetch_return_matrix

load_env()
log = get_logger("risk_corr")


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _corr(x: Sequence[float], y: Sequence[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    xs = [float(v) for v in x[-n:]]
    ys = [float(v) for v in y[-n:]]
    mx = _mean(xs)
    my = _mean(ys)
    vx = sum((v - mx) ** 2 for v in xs)
    vy = sum((v - my) ** 2 for v in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    return float(cov / math.sqrt(vx * vy))


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _coerce_matrix(returns_matrix) -> Dict[str, List[float]]:
    if returns_matrix is None:
        return {}
    if hasattr(returns_matrix, "to_dict"):
        try:
            cols = list(getattr(returns_matrix, "columns", []))
            out = {}
            for c in cols:
                series = list(returns_matrix[c])
                out[_normalize_symbol(c)] = [_safe_float(v) for v in series]
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


def correlation_matrix(returns_matrix, window: int = 60) -> Dict[str, Dict[str, float]]:
    matrix = _coerce_matrix(returns_matrix)
    syms = sorted([s for s, v in matrix.items() if len(v) >= 2])
    out: Dict[str, Dict[str, float]] = {s: {} for s in syms}

    for i, a in enumerate(syms):
        xa = matrix[a][-max(window, 2) :]
        for b in syms[i:]:
            xb = matrix[b][-max(window, 2) :]
            c = 1.0 if a == b else _corr(xa, xb)
            out[a][b] = c
            if a != b:
                out[b][a] = c
    return out


def find_high_correlation_pairs(
    corr_matrix: Dict[str, Dict[str, float]],
    threshold: float = 0.7,
) -> List[dict]:
    rows = []
    syms = sorted(corr_matrix.keys())
    for i, a in enumerate(syms):
        for b in syms[i + 1 :]:
            c = _safe_float((corr_matrix.get(a) or {}).get(b), 0.0)
            if c >= threshold:
                rows.append({"a": a, "b": b, "corr": round(c, 4)})
    rows.sort(key=lambda x: x["corr"], reverse=True)
    return rows


def detect_correlation_spikes(
    corr_matrix: Dict[str, Dict[str, float]],
    prev_matrix: Dict[str, Dict[str, float]] | None,
    delta_threshold: float = 0.2,
) -> List[dict]:
    if not prev_matrix:
        return []
    spikes = []
    syms = sorted(corr_matrix.keys())
    for i, a in enumerate(syms):
        for b in syms[i + 1 :]:
            cur = _safe_float((corr_matrix.get(a) or {}).get(b), 0.0)
            prv = _safe_float((prev_matrix.get(a) or {}).get(b), 0.0)
            delta = cur - prv
            if delta >= delta_threshold:
                spikes.append(
                    {
                        "a": a,
                        "b": b,
                        "prev": round(prv, 4),
                        "curr": round(cur, 4),
                        "delta": round(delta, 4),
                    }
                )
    spikes.sort(key=lambda x: x["delta"], reverse=True)
    return spikes


class CorrelationMonitor:
    def __init__(
        self,
        window: int = 60,
        corr_threshold: float = 0.7,
        spike_delta: float = 0.2,
        cache_key_prefix: str = "risk:corr",
    ):
        self.window = max(window, 5)
        self.corr_threshold = corr_threshold
        self.spike_delta = spike_delta
        self.cache_key_prefix = cache_key_prefix

    def evaluate(
        self,
        returns_matrix,
        label: str = "portfolio",
        send_alert: bool = True,
    ) -> dict:
        corr = correlation_matrix(returns_matrix, window=self.window)
        prev_key = f"{self.cache_key_prefix}:{label}:latest"
        prev = get_cached(prev_key)

        highs = find_high_correlation_pairs(corr, threshold=self.corr_threshold)
        spikes = detect_correlation_spikes(corr, prev, delta_threshold=self.spike_delta)

        set_cached(prev_key, corr, ttl=3600)

        alert_sent = False
        if send_alert and (highs or spikes):
            msg = self._build_alert_message(highs, spikes)
            if msg:
                alert_sent = send_telegram(msg)

        return {
            "window": self.window,
            "corr_threshold": self.corr_threshold,
            "spike_delta": self.spike_delta,
            "high_pairs": highs,
            "spikes": spikes,
            "alert_sent": alert_sent,
            "correlation_matrix": corr,
        }

    def evaluate_from_symbols(
        self,
        symbols: List[str],
        lookback_days: int = 120,
        label: str = "portfolio",
        send_alert: bool = True,
    ) -> dict:
        matrix = fetch_return_matrix(symbols, lookback_days=max(lookback_days, self.window + 5))
        if not matrix:
            return {
                "window": self.window,
                "high_pairs": [],
                "spikes": [],
                "alert_sent": False,
                "correlation_matrix": {},
            }
        return self.evaluate(matrix, label=label, send_alert=send_alert)

    def _build_alert_message(self, highs: List[dict], spikes: List[dict]) -> str:
        lines = ["⚠️ <b>Correlation Risk Alert</b>"]
        if highs:
            lines.append("\n상관>임계치:")
            for row in highs[:8]:
                lines.append(f"- {row['a']} vs {row['b']}: {row['corr']:.2f}")
        if spikes:
            lines.append("\n상관 급등:")
            for row in spikes[:8]:
                lines.append(f"- {row['a']} vs {row['b']}: {row['prev']:.2f} → {row['curr']:.2f} (+{row['delta']:.2f})")
        return "\n".join(lines)


if __name__ == "__main__":
    monitor = CorrelationMonitor(window=60, corr_threshold=0.7)
    out = monitor.evaluate_from_symbols(["BTC-USD", "AAPL", "MSFT", "005930.KS"], send_alert=False)
    log.info("correlation_monitor", high_pairs=len(out.get("high_pairs", [])), spikes=len(out.get("spikes", [])))
