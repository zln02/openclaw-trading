"""BTC whale activity tracker (Phase 14).

Tracks exchange inflow/outflow surges and long-term holder (LTH) movement.
Data source priority:
1) Glassnode API (if GLASSNODE_API_KEY exists)
2) lightweight fallback from common.market_data
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import requests

from common.env_loader import load_env
from common.logger import get_logger
from common.market_data import get_btc_whale_activity
from common.retry import retry_call

load_env()
log = get_logger("btc_whale_tracker")

GLASSNODE_BASE = "https://api.glassnode.com/v1/metrics"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _ratio(cur: float, baseline: float) -> float:
    c = max(_safe_float(cur, 0.0), 0.0)
    b = max(_safe_float(baseline, 0.0), 0.0)
    if b <= 0:
        return 0.0
    return c / b


def classify_whale_activity(
    inflow_btc: float,
    outflow_btc: float,
    inflow_avg_btc: float,
    outflow_avg_btc: float,
    lth_moved_btc: float = 0.0,
    lth_avg_btc: float = 0.0,
) -> dict:
    inflow = max(_safe_float(inflow_btc, 0.0), 0.0)
    outflow = max(_safe_float(outflow_btc, 0.0), 0.0)
    inflow_ratio = _ratio(inflow, inflow_avg_btc)
    outflow_ratio = _ratio(outflow, outflow_avg_btc)
    lth_ratio = _ratio(max(_safe_float(lth_moved_btc, 0.0), 0.0), max(_safe_float(lth_avg_btc, 0.0), 0.0))

    signal = "NEUTRAL"
    pressure = 0.0
    reason = "balanced exchange flows"

    if inflow_ratio >= 1.8 and inflow > outflow:
        signal = "SELL_PRESSURE"
        pressure = -1.0
        reason = f"exchange inflow surge ({inflow_ratio:.2f}x)"
    elif outflow_ratio >= 1.8 and outflow > inflow:
        signal = "HODL_SIGNAL"
        pressure = 1.0
        reason = f"exchange outflow surge ({outflow_ratio:.2f}x)"

    if lth_ratio >= 2.0:
        if signal == "SELL_PRESSURE":
            signal = "LTH_DISTRIBUTION_RISK"
            pressure = -1.25
            reason += " + LTH movement spike"
        else:
            signal = "LTH_MOVEMENT_ALERT"
            reason = f"LTH moved {lth_ratio:.2f}x baseline"

    return {
        "signal": signal,
        "pressure_score": round(pressure, 4),
        "reason": reason,
        "inflow_ratio": round(inflow_ratio, 4),
        "outflow_ratio": round(outflow_ratio, 4),
        "lth_ratio": round(lth_ratio, 4),
    }


@dataclass
class WhaleSnapshot:
    exchange_inflow_btc: float
    exchange_outflow_btc: float
    inflow_avg_btc: float
    outflow_avg_btc: float
    lth_moved_btc: float
    lth_avg_btc: float
    signal: str
    pressure_score: float
    reason: str
    source: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class WhaleTracker:
    def __init__(self, provider: Optional[Callable[[], dict]] = None):
        self.provider = provider or self._default_provider

    def _glassnode_last_value(self, endpoint: str, api_key: str) -> tuple[float, float]:
        url = f"{GLASSNODE_BASE}/{endpoint}"
        resp = retry_call(
            requests.get,
            args=(url,),
            kwargs={
                "params": {"a": "BTC", "i": "24h", "api_key": api_key},
                "timeout": 8,
            },
            max_attempts=2,
            base_delay=0.7,
            default=None,
        )
        if resp is None or not getattr(resp, "ok", False):
            return 0.0, 0.0

        try:
            rows = resp.json() or []
            vals = [_safe_float(r.get("v"), 0.0) for r in rows if isinstance(r, dict)]
            vals = [v for v in vals if v >= 0]
            if not vals:
                return 0.0, 0.0
            cur = vals[-1]
            baseline = sum(vals[-8:-1]) / max(len(vals[-8:-1]), 1)
            return cur, baseline
        except Exception:
            return 0.0, 0.0

    def _fetch_glassnode(self) -> Optional[dict]:
        api_key = os.environ.get("GLASSNODE_API_KEY", "")
        if not api_key:
            return None

        inflow, inflow_avg = self._glassnode_last_value(
            "transactions/transfers_volume_to_exchanges_sum",
            api_key,
        )
        outflow, outflow_avg = self._glassnode_last_value(
            "transactions/transfers_volume_from_exchanges_sum",
            api_key,
        )

        # LTH proxy: active supply 1y+ changes (absolute daily change)
        lth_cur, lth_avg = self._glassnode_last_value("supply/active_1y_plus", api_key)
        if inflow <= 0 and outflow <= 0 and lth_cur <= 0:
            return None

        return {
            "exchange_inflow_btc": inflow,
            "exchange_outflow_btc": outflow,
            "inflow_avg_btc": inflow_avg,
            "outflow_avg_btc": outflow_avg,
            "lth_moved_btc": lth_cur,
            "lth_avg_btc": lth_avg,
            "source": "glassnode",
        }

    def _default_provider(self) -> dict:
        gn = self._fetch_glassnode()
        if gn is not None:
            return gn

        # Fallback path: coarse activity proxy using existing free endpoint wrapper.
        row = get_btc_whale_activity() or {}
        unconfirmed = max(_safe_float(row.get("unconfirmed_tx"), 0.0), 0.0)

        inflow = unconfirmed * 0.015
        outflow = unconfirmed * 0.013
        baseline = max(unconfirmed * 0.010, 1.0)

        return {
            "exchange_inflow_btc": inflow,
            "exchange_outflow_btc": outflow,
            "inflow_avg_btc": baseline,
            "outflow_avg_btc": baseline,
            "lth_moved_btc": unconfirmed * 0.002,
            "lth_avg_btc": max(unconfirmed * 0.0015, 0.1),
            "source": "fallback_market_data",
        }

    def snapshot(self) -> dict:
        raw = self.provider() or {}

        inflow = _safe_float(raw.get("exchange_inflow_btc"), 0.0)
        outflow = _safe_float(raw.get("exchange_outflow_btc"), 0.0)
        inflow_avg = _safe_float(raw.get("inflow_avg_btc"), 0.0)
        outflow_avg = _safe_float(raw.get("outflow_avg_btc"), 0.0)
        lth_move = _safe_float(raw.get("lth_moved_btc"), 0.0)
        lth_avg = _safe_float(raw.get("lth_avg_btc"), 0.0)

        cls = classify_whale_activity(
            inflow_btc=inflow,
            outflow_btc=outflow,
            inflow_avg_btc=inflow_avg,
            outflow_avg_btc=outflow_avg,
            lth_moved_btc=lth_move,
            lth_avg_btc=lth_avg,
        )

        out = WhaleSnapshot(
            exchange_inflow_btc=round(inflow, 6),
            exchange_outflow_btc=round(outflow, 6),
            inflow_avg_btc=round(inflow_avg, 6),
            outflow_avg_btc=round(outflow_avg, 6),
            lth_moved_btc=round(lth_move, 6),
            lth_avg_btc=round(lth_avg, 6),
            signal=str(cls.get("signal") or "NEUTRAL"),
            pressure_score=_safe_float(cls.get("pressure_score"), 0.0),
            reason=str(cls.get("reason") or ""),
            source=str(raw.get("source") or "unknown"),
            timestamp=_utc_now_iso(),
        )
        return out.to_dict()


def _cli() -> int:
    parser = argparse.ArgumentParser(description="BTC whale tracker")
    parser.add_argument("--inflow", type=float, default=None, help="manual inflow BTC")
    parser.add_argument("--outflow", type=float, default=None, help="manual outflow BTC")
    parser.add_argument("--inflow-avg", type=float, default=0.0)
    parser.add_argument("--outflow-avg", type=float, default=0.0)
    parser.add_argument("--lth", type=float, default=0.0)
    parser.add_argument("--lth-avg", type=float, default=0.0)
    args = parser.parse_args()

    if args.inflow is not None and args.outflow is not None:
        cls = classify_whale_activity(
            inflow_btc=args.inflow,
            outflow_btc=args.outflow,
            inflow_avg_btc=args.inflow_avg,
            outflow_avg_btc=args.outflow_avg,
            lth_moved_btc=args.lth,
            lth_avg_btc=args.lth_avg,
        )
        out = {
            "exchange_inflow_btc": args.inflow,
            "exchange_outflow_btc": args.outflow,
            "inflow_avg_btc": args.inflow_avg,
            "outflow_avg_btc": args.outflow_avg,
            "lth_moved_btc": args.lth,
            "lth_avg_btc": args.lth_avg,
            **cls,
            "timestamp": _utc_now_iso(),
            "source": "manual",
        }
    else:
        out = WhaleTracker().snapshot()

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
