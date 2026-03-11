"""DRY-RUN DEX arbitrage executor (Phase D-2)."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.config import (
    BRAIN_PATH,
    MAX_ARB_SLIPPAGE_BPS,
    MAX_GAS_GWEI,
    MIN_ARB_PROFIT_USD,
)
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram

load_env()
log = get_logger("arb_executor")
supabase = get_supabase()

SNAPSHOT_PATH = BRAIN_PATH / "arb" / "dex_monitor.json"
RESULT_PATH = BRAIN_PATH / "arb" / "arb_execution.json"
DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"
TABLE = "arb_opportunities"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def load_snapshot(path: Path = SNAPSHOT_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def evaluate_snapshot(snapshot: dict) -> dict:
    arb = snapshot.get("arb") or {}
    cex = snapshot.get("cex") or {}
    dex = snapshot.get("dex") or {}

    net_profit = _safe_float(arb.get("net_profit_usd"), 0.0)
    gas_gwei = _safe_float(arb.get("gas_gwei"), 0.0)
    slippage_bps = _safe_float(arb.get("slippage_bps"), 0.0)
    direction = str(snapshot.get("direction") or "unknown")

    checks = {
        "has_snapshot": bool(snapshot),
        "status_opportunity": str(snapshot.get("status") or "") == "OPPORTUNITY",
        "profit_ok": net_profit > MIN_ARB_PROFIT_USD,
        "gas_ok": gas_gwei < MAX_GAS_GWEI,
        "slippage_ok": slippage_bps < MAX_ARB_SLIPPAGE_BPS,
        "direction_ok": direction in {"cex_to_dex", "dex_to_cex"},
        "price_ok": _safe_float(cex.get("upbit_usd"), 0.0) > 0 and _safe_float(dex.get("best_price_usd"), 0.0) > 0,
    }
    trigger = all(checks.values())

    return {
        "timestamp": _utc_now_iso(),
        "trigger": trigger,
        "mode": "DRY_RUN" if DRY_RUN else "LIVE",
        "checks": checks,
        "direction": direction,
        "cex_price": round(_safe_float(cex.get("upbit_usd"), 0.0), 6),
        "dex_price": round(_safe_float(dex.get("best_price_usd"), 0.0), 6),
        "spread_pct": round(_safe_float(arb.get("cross_arb_pct"), 0.0), 6),
        "gas_cost_usd": round(_safe_float(arb.get("gas_cost_usd"), 0.0), 4),
        "net_profit_usd": round(net_profit, 4),
        "pair": str(dex.get("best_pair") or "unavailable"),
        "executed": False,
        "tx_hash": None,
        "reason": "ready" if trigger else _failure_reason(checks, net_profit, gas_gwei, slippage_bps),
    }


def _failure_reason(checks: dict, net_profit: float, gas_gwei: float, slippage_bps: float) -> str:
    if not checks.get("has_snapshot"):
        return "no snapshot"
    if not checks.get("status_opportunity"):
        return "snapshot not opportunity"
    if not checks.get("profit_ok"):
        return f"net_profit {net_profit:.2f} <= {MIN_ARB_PROFIT_USD:.2f}"
    if not checks.get("gas_ok"):
        return f"gas {gas_gwei:.2f} >= {MAX_GAS_GWEI:.2f}"
    if not checks.get("slippage_ok"):
        return f"slippage {slippage_bps:.2f} >= {MAX_ARB_SLIPPAGE_BPS:.2f}"
    if not checks.get("direction_ok"):
        return "direction unknown"
    if not checks.get("price_ok"):
        return "missing prices"
    return "blocked"


def persist_opportunity(result: dict) -> None:
    if not supabase:
        return
    payload = {
        "direction": result.get("direction"),
        "cex_price": result.get("cex_price"),
        "dex_price": result.get("dex_price"),
        "spread_pct": result.get("spread_pct"),
        "gas_cost_usd": result.get("gas_cost_usd"),
        "net_profit_usd": result.get("net_profit_usd"),
        "executed": bool(result.get("executed")),
        "tx_hash": result.get("tx_hash"),
    }
    try:
        supabase.table(TABLE).insert(payload).execute()
    except Exception as exc:
        log.warning("arb opportunity persist failed", error=str(exc))


def save_result(result: dict) -> Path:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return RESULT_PATH


def maybe_notify(result: dict) -> None:
    if not result.get("trigger"):
        return
    send_telegram(
        "\n".join(
            [
                "⚡ <b>DEX Arb Execution Candidate</b>",
                f"Mode: {result.get('mode')}",
                f"Direction: {result.get('direction')}",
                f"Spread: {float(result.get('spread_pct', 0.0) or 0.0):+.2f}%",
                f"Net Profit: ${float(result.get('net_profit_usd', 0.0) or 0.0):+.2f}",
            ]
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="DRY-RUN arbitrage executor")
    parser.add_argument("--snapshot-file", default=str(SNAPSHOT_PATH))
    parser.add_argument("--no-send", action="store_true")
    args = parser.parse_args()

    snapshot = load_snapshot(Path(args.snapshot_file))
    result = evaluate_snapshot(snapshot)
    path = save_result(result)
    persist_opportunity(result)
    log.info("arb execution evaluated", trigger=result.get("trigger"), reason=result.get("reason"), path=str(path))
    if not args.no_send:
        maybe_notify(result)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
