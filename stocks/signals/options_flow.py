"""US options-flow analyzer (Phase 16)."""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("options_flow")

POLYGON_OPTIONS_SNAPSHOT_URL = "https://api.polygon.io/v3/snapshot/options/{symbol}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


@dataclass
class OptionsFlowSignal:
    symbol: str
    call_volume: float
    put_volume: float
    put_call_ratio: float
    put_call_ratio_change: float
    unusual_call: bool
    unusual_put: bool
    bias: str
    confidence: float
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_options_flow(
    symbol: str,
    call_volume: float,
    put_volume: float,
    avg_call_volume: float,
    avg_put_volume: float,
    prev_put_call_ratio: Optional[float] = None,
    call_notional: float = 0.0,
    put_notional: float = 0.0,
) -> dict:
    calls = max(_safe_float(call_volume, 0.0), 0.0)
    puts = max(_safe_float(put_volume, 0.0), 0.0)
    avg_calls = max(_safe_float(avg_call_volume, 0.0), 1e-9)
    avg_puts = max(_safe_float(avg_put_volume, 0.0), 1e-9)

    pcr = puts / calls if calls > 0 else (999.0 if puts > 0 else 1.0)
    prev = _safe_float(prev_put_call_ratio, pcr)
    pcr_change = pcr - prev

    unusual_call = calls >= avg_calls * 2.0
    unusual_put = puts >= avg_puts * 2.0

    bias = "NEUTRAL"
    confidence = 50.0
    reasons: list[str] = []

    call_cash = max(_safe_float(call_notional, 0.0), 0.0)
    put_cash = max(_safe_float(put_notional, 0.0), 0.0)

    if unusual_call and pcr < 0.9 and call_cash >= put_cash:
        bias = "BULLISH"
        confidence += 25.0
        reasons.append("unusual call accumulation")
    elif unusual_put and pcr > 1.2 and put_cash >= call_cash:
        bias = "BEARISH"
        confidence += 25.0
        reasons.append("unusual put accumulation")

    if pcr_change <= -0.25:
        confidence += 8.0
        reasons.append("PCR falling fast")
        if bias == "NEUTRAL":
            bias = "BULLISH"
    elif pcr_change >= 0.25:
        confidence += 8.0
        reasons.append("PCR rising fast")
        if bias == "NEUTRAL":
            bias = "BEARISH"

    confidence = max(0.0, min(confidence, 100.0))

    if not reasons:
        reasons.append("no unusual option flow")

    out = OptionsFlowSignal(
        symbol=str(symbol or "").upper(),
        call_volume=round(calls, 2),
        put_volume=round(puts, 2),
        put_call_ratio=round(pcr, 6),
        put_call_ratio_change=round(pcr_change, 6),
        unusual_call=bool(unusual_call),
        unusual_put=bool(unusual_put),
        bias=bias,
        confidence=round(confidence, 2),
        reason="; ".join(reasons),
        timestamp=_utc_now_iso(),
    )
    return out.to_dict()


class OptionsFlowAnalyzer:
    def __init__(self, polygon_api_key: Optional[str] = None):
        self.polygon_api_key = polygon_api_key or os.environ.get("POLYGON_API_KEY", "")

    def fetch_polygon_snapshot(self, symbol: str) -> dict:
        if not self.polygon_api_key:
            return {}

        url = POLYGON_OPTIONS_SNAPSHOT_URL.format(symbol=str(symbol or "").upper())
        resp = retry_call(
            requests.get,
            args=(url,),
            kwargs={
                "params": {"apiKey": self.polygon_api_key, "limit": 250},
                "timeout": 10,
            },
            max_attempts=2,
            base_delay=0.8,
            default=None,
        )
        if resp is None or not getattr(resp, "ok", False):
            return {}

        try:
            return resp.json() or {}
        except Exception:
            return {}

    def summarize_snapshot(self, symbol: str, snapshot: dict, prev_put_call_ratio: Optional[float] = None) -> dict:
        rows = snapshot.get("results") if isinstance(snapshot, dict) else []
        if not isinstance(rows, list):
            rows = []

        call_vol = 0.0
        put_vol = 0.0
        call_oi = 0.0
        put_oi = 0.0

        for row in rows:
            if not isinstance(row, dict):
                continue
            details = row.get("details") or {}
            day = row.get("day") or {}
            contract_type = str(details.get("contract_type") or "").lower()
            vol = _safe_float(day.get("volume"), 0.0)
            oi = _safe_float(row.get("open_interest"), 0.0)

            if contract_type == "call":
                call_vol += vol
                call_oi += oi
            elif contract_type == "put":
                put_vol += vol
                put_oi += oi

        avg_call = call_oi / max(len(rows), 1)
        avg_put = put_oi / max(len(rows), 1)

        return analyze_options_flow(
            symbol=symbol,
            call_volume=call_vol,
            put_volume=put_vol,
            avg_call_volume=max(avg_call, 1.0),
            avg_put_volume=max(avg_put, 1.0),
            prev_put_call_ratio=prev_put_call_ratio,
            call_notional=call_vol,
            put_notional=put_vol,
        )

    def analyze(
        self,
        symbol: str,
        call_volume: Optional[float] = None,
        put_volume: Optional[float] = None,
        avg_call_volume: Optional[float] = None,
        avg_put_volume: Optional[float] = None,
        prev_put_call_ratio: Optional[float] = None,
    ) -> dict:
        if call_volume is not None and put_volume is not None and avg_call_volume is not None and avg_put_volume is not None:
            return analyze_options_flow(
                symbol=symbol,
                call_volume=call_volume,
                put_volume=put_volume,
                avg_call_volume=avg_call_volume,
                avg_put_volume=avg_put_volume,
                prev_put_call_ratio=prev_put_call_ratio,
            )

        snap = self.fetch_polygon_snapshot(symbol)
        return self.summarize_snapshot(symbol, snap, prev_put_call_ratio=prev_put_call_ratio)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="US options flow analyzer")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--calls", type=float, default=None)
    parser.add_argument("--puts", type=float, default=None)
    parser.add_argument("--avg-calls", type=float, default=None)
    parser.add_argument("--avg-puts", type=float, default=None)
    parser.add_argument("--prev-pcr", type=float, default=None)
    args = parser.parse_args()

    out = OptionsFlowAnalyzer().analyze(
        symbol=args.symbol,
        call_volume=args.calls,
        put_volume=args.puts,
        avg_call_volume=args.avg_calls,
        avg_put_volume=args.avg_puts,
        prev_put_call_ratio=args.prev_pcr,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
