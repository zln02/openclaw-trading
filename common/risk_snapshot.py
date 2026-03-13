from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import BRAIN_PATH
from common.equity_loader import load_all_positions
from quant.risk.var_model import VaRModel, fetch_return_matrix


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _equity_snapshot_path(market: str) -> Path:
    return BRAIN_PATH / "equity" / f"{market}.jsonl"


def _risk_snapshot_path() -> Path:
    return BRAIN_PATH / "risk" / "latest_snapshot.json"


def _proxy_symbol(symbol: str) -> str:
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


def _load_latest_equity_series(days: int = 60) -> dict[str, float]:
    cutoff = (_utc_now().date() - timedelta(days=max(days, 30))).isoformat()
    merged: dict[str, dict[str, float]] = {}
    for market in ("btc", "kr", "us"):
        path = _equity_snapshot_path(market)
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                day = str(row.get("date") or "")[:10]
                if not day or day < cutoff:
                    continue
                equity = _safe_float(row.get("equity"), 0.0)
                if equity <= 0:
                    continue
                merged.setdefault(day, {})[market] = equity
        except Exception:
            continue

    return {day: round(sum(markets.values()), 6) for day, markets in merged.items() if markets}


def _compute_drawdown_from_equity(total_equity_by_day: dict[str, float]) -> float:
    if not total_equity_by_day:
        return 0.0
    peak = 0.0
    max_dd = 0.0
    for day in sorted(total_equity_by_day.keys()):
        eq = _safe_float(total_equity_by_day[day], 0.0)
        if eq <= 0:
            continue
        peak = max(peak, eq)
        if peak > 0:
            dd = eq / peak - 1.0
            max_dd = min(max_dd, dd)
    return round(max_dd, 6)


def build_risk_snapshot(lookback_days: int = 252) -> dict:
    positions = load_all_positions()
    proxy_map = {}
    for pos in positions:
        symbol = str(pos.get("symbol") or "").upper()
        proxy = _proxy_symbol(symbol)
        if symbol and proxy:
            proxy_map[symbol] = proxy

    returns_proxy = fetch_return_matrix(list(proxy_map.values()), lookback_days=lookback_days)
    returns_252d = {}
    for symbol, proxy in proxy_map.items():
        series = returns_proxy.get(proxy)
        if series:
            returns_252d[symbol] = series

    var_metrics = VaRModel(lookback_days=lookback_days).compute(positions, returns_252d) if returns_252d else {}
    total_equity_by_day = _load_latest_equity_series(days=90)
    snapshot = {
        "timestamp": _utc_now().isoformat(),
        "positions": positions,
        "returns_252d": returns_252d,
        "drawdown": _compute_drawdown_from_equity(total_equity_by_day),
        "var_95": _safe_float(var_metrics.get("var_95"), 0.0),
        "var_99": _safe_float(var_metrics.get("var_99"), 0.0),
        "cvar_95": _safe_float(var_metrics.get("cvar_95"), 0.0),
        "portfolio_vol": _safe_float(var_metrics.get("portfolio_vol"), 0.0),
        "diversification_ratio": _safe_float(var_metrics.get("diversification_ratio"), 1.0),
        "symbols": sorted(returns_252d.keys()),
    }
    return snapshot


def save_risk_snapshot(snapshot: dict) -> Path:
    path = _risk_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    out = build_risk_snapshot()
    path = save_risk_snapshot(out)
    print(path)
