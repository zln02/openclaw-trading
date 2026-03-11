"""Cross-market portfolio manager (Phase C-1).

Builds a daily market allocation budget across BTC/KR/US/CASH.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agents.regime_classifier import RegimeClassifier
from common.config import BRAIN_PATH
from common.equity_loader import load_all_positions, load_recent_trades
from common.logger import get_logger
from quant.risk.var_model import VaRModel, fetch_return_matrix

log = get_logger("cross_market_manager")

BASE_ALLOCATION = {"btc": 0.30, "kr": 0.40, "us": 0.30, "cash": 0.00}
REGIME_ALLOCATION = {
    "CRISIS": {"btc": 0.15, "kr": 0.25, "us": 0.25, "cash": 0.35},
    "RISK_OFF": {"btc": 0.20, "kr": 0.35, "us": 0.25, "cash": 0.20},
    "TRANSITION": {"btc": 0.30, "kr": 0.40, "us": 0.30, "cash": 0.00},
    "RISK_ON": {"btc": 0.35, "kr": 0.40, "us": 0.25, "cash": 0.00},
}
MARKETS = ("btc", "kr", "us")
MAX_MARKET_VAR = 0.03
IC_SHIFT_STEP = 0.05


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _output_path() -> Path:
    return BRAIN_PATH / "portfolio" / "market_allocation.json"


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    clean = {k: max(_safe_float(v, 0.0), 0.0) for k, v in weights.items() if k}
    total = sum(clean.values())
    if total <= 0:
        return dict(BASE_ALLOCATION)
    return {k: v / total for k, v in clean.items()}


def _position_proxy(symbol: str) -> str:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return ""
    if sym == "BTC":
        return "BTC-USD"
    if sym.startswith("A") and sym[1:].isdigit():
        return f"{sym[1:]}.KS"
    if sym.isdigit():
        return f"{sym}.KS"
    return sym


def _recent_market_score(market: str, lookback_days: int = 30) -> dict[str, float]:
    trades = load_recent_trades(market, limit=max(lookback_days * 4, 60))
    cutoff = (_utc_now().date() - timedelta(days=max(lookback_days, 7))).isoformat()
    samples = [float(t.get("pnl_pct", 0.0) or 0.0) for t in trades if str(t.get("date", "")) >= cutoff]
    if not samples:
        return {"score": 0.0, "mean_pnl": 0.0, "win_rate": 0.0, "count": 0}
    wins = [x for x in samples if x > 0]
    mean_pnl = sum(samples) / len(samples)
    win_rate = len(wins) / len(samples)
    score = round(mean_pnl * 0.6 + (win_rate - 0.5) * 0.4, 6)
    return {
        "score": score,
        "mean_pnl": round(mean_pnl, 6),
        "win_rate": round(win_rate, 6),
        "count": len(samples),
    }


def _market_var_by_bucket(lookback_days: int = 252) -> dict[str, float]:
    positions = load_all_positions()
    if not positions:
        return {market: 0.0 for market in MARKETS}

    proxy_map = {}
    grouped: dict[str, list[dict]] = {market: [] for market in MARKETS}
    for pos in positions:
        market = str(pos.get("market") or "").lower()
        if market not in grouped:
            continue
        grouped[market].append(pos)
        symbol = str(pos.get("symbol") or "").upper()
        proxy = _position_proxy(symbol)
        if proxy:
            proxy_map[symbol] = proxy

    returns_proxy = fetch_return_matrix(list(set(proxy_map.values())), lookback_days=lookback_days)
    var_model = VaRModel(lookback_days=lookback_days)
    out: dict[str, float] = {}
    for market in MARKETS:
        returns_252d = {}
        for pos in grouped[market]:
            symbol = str(pos.get("symbol") or "").upper()
            proxy = proxy_map.get(symbol)
            if proxy and returns_proxy.get(proxy):
                returns_252d[symbol] = returns_proxy[proxy]
        if grouped[market] and returns_252d:
            metrics = var_model.compute(grouped[market], returns_252d)
            out[market] = _safe_float(metrics.get("var_99"), 0.0)
        else:
            out[market] = 0.0
    return out


def _apply_ic_shift(allocation: dict[str, float], market_scores: dict[str, dict[str, float]]) -> dict[str, float]:
    eligible = [(market, stats.get("score", 0.0)) for market, stats in market_scores.items() if stats.get("count", 0) >= 5]
    if not eligible:
        return dict(allocation)

    winner, winner_score = max(eligible, key=lambda item: item[1])
    loser, loser_score = min(eligible, key=lambda item: item[1])
    shifted = dict(allocation)

    if winner != loser and winner_score > 0 and loser_score < 0:
        shift = min(IC_SHIFT_STEP, shifted.get(loser, 0.0), 1.0 - shifted.get(winner, 0.0))
        shifted[winner] = shifted.get(winner, 0.0) + shift
        shifted[loser] = max(0.0, shifted.get(loser, 0.0) - shift)
    return shifted


def _apply_var_caps(allocation: dict[str, float], market_vars: dict[str, float]) -> dict[str, float]:
    capped = dict(allocation)
    freed = 0.0
    for market, var_99 in market_vars.items():
        if market not in capped:
            continue
        if var_99 > MAX_MARKET_VAR:
            reduction = min(0.05, capped[market] * 0.20)
            capped[market] = max(0.0, capped[market] - reduction)
            freed += reduction
    capped["cash"] = capped.get("cash", 0.0) + freed
    return capped


def build_market_allocation() -> dict:
    regime_result = RegimeClassifier().classify()
    regime = str(regime_result.get("regime", "TRANSITION")).upper()
    allocation = dict(REGIME_ALLOCATION.get(regime, BASE_ALLOCATION))
    market_scores = {market: _recent_market_score(market) for market in MARKETS}
    market_vars = _market_var_by_bucket()

    allocation = _apply_ic_shift(allocation, market_scores)
    allocation = _apply_var_caps(allocation, market_vars)
    allocation = _normalize(allocation)

    return {
        "timestamp": _utc_now().isoformat(),
        "base_allocation": BASE_ALLOCATION,
        "regime": regime,
        "regime_source": regime_result.get("source", "unknown"),
        "allocation": {k: round(v, 6) for k, v in allocation.items()},
        "market_scores": market_scores,
        "market_var_99": {k: round(v, 6) for k, v in market_vars.items()},
        "constraints": {
            "max_market_var": MAX_MARKET_VAR,
            "ic_shift_step": IC_SHIFT_STEP,
        },
    }


def save_market_allocation(payload: dict) -> Path:
    path = _output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-market portfolio manager")
    parser.add_argument("--print", action="store_true", dest="do_print", help="print JSON after saving")
    args = parser.parse_args()

    payload = build_market_allocation()
    path = save_market_allocation(payload)
    log.info(
        "market allocation saved",
        path=str(path),
        regime=payload.get("regime"),
        allocation=payload.get("allocation"),
    )
    if args.do_print:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
