"""VWAP execution algorithm (Phase 13).

Input:
- { symbol, side, total_qty, duration_minutes }

Output:
- volume-weighted schedule + fills
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from common.data.realtime_price import get_price_snapshot
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call
from common.supabase_client import get_supabase

load_env()
log = get_logger("execution_vwap")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_side(side: str) -> str:
    s = str(side or "").strip().lower()
    if s in {"buy", "sell"}:
        return s
    raise ValueError(f"invalid side: {side}")


def _infer_market(symbol: str, market: str = "auto") -> str:
    mk = str(market or "auto").strip().lower()
    if mk in {"btc", "kr", "us"}:
        return mk

    sym = str(symbol or "").upper()
    if sym.startswith("KRW-") or sym.endswith("USDT") or sym == "BTC":
        return "btc"
    if sym.isdigit() or (sym.startswith("A") and sym[1:].isdigit()):
        return "kr"
    return "us"


def _default_u_curve(n: int) -> List[float]:
    n = max(1, int(n))
    if n == 1:
        return [1.0]

    weights = []
    for i in range(n):
        x = i / (n - 1)
        # U-curve: edges high, middle low
        w = 0.85 + 0.55 * (abs(x - 0.5) * 2.0)
        weights.append(w)

    s = sum(weights)
    if s <= 0:
        return [1.0 / n] * n
    return [w / s for w in weights]


def _normalize_weights(weights: List[float], fallback_n: int) -> List[float]:
    if not weights:
        return _default_u_curve(fallback_n)

    cleaned = [max(_safe_float(w), 0.0) for w in weights]
    total = sum(cleaned)
    if total <= 0:
        return _default_u_curve(fallback_n)
    return [w / total for w in cleaned]


def _bucketize(values: List[float], buckets: int) -> List[float]:
    n = len(values)
    b = max(1, int(buckets))
    if n == 0:
        return []

    out: List[float] = []
    for i in range(b):
        left = int(i * n / b)
        right = int((i + 1) * n / b)
        if right <= left:
            right = min(left + 1, n)
        chunk = values[left:right]
        out.append(sum(chunk) if chunk else 0.0)
    return out


def _fetch_intraday_volume_series(
    symbol: str,
    market: str,
    lookback_days: int = 5,
    supabase_client=None,
) -> List[float]:
    mk = _infer_market(symbol, market)
    sym = str(symbol or "").upper()

    if mk == "kr":
        code = sym.lstrip("A")
        sb = supabase_client or get_supabase()
        if sb is not None:
            try:
                start_iso = (datetime.now(timezone.utc) - timedelta(days=max(lookback_days, 1))).isoformat()
                rows = (
                    sb.table("intraday_ohlcv")
                    .select("datetime,volume")
                    .eq("stock_code", code)
                    .eq("time_interval", "5m")
                    .gte("datetime", start_iso)
                    .order("datetime")
                    .execute()
                    .data
                    or []
                )
                vols = [_safe_float(r.get("volume"), 0.0) for r in rows]
                vols = [v for v in vols if v > 0]
                if vols:
                    return vols
            except Exception as exc:
                log.warn("supabase intraday volume fetch failed", symbol=code, error=exc)

    try:
        import yfinance as yf

        yf_symbol = sym
        if mk == "kr" and sym.isdigit():
            yf_symbol = f"{sym}.KS"
        elif mk == "btc":
            yf_symbol = "BTC-USD"

        hist = retry_call(
            yf.Ticker(yf_symbol).history,
            kwargs={"period": f"{max(lookback_days, 1)}d", "interval": "5m"},
            max_attempts=2,
            base_delay=1.0,
            default=None,
        )
        if hist is not None and not hist.empty and "Volume" in hist:
            vols = [_safe_float(v, 0.0) for v in list(hist["Volume"]) if _safe_float(v, 0.0) > 0]
            if vols:
                return vols
    except Exception as exc:
        log.warn("yfinance intraday volume fetch failed", symbol=sym, error=exc)

    if mk == "btc":
        try:
            import pyupbit

            count = max(24, min(lookback_days * 24 * 12, 1440))
            df = retry_call(
                pyupbit.get_ohlcv,
                args=("KRW-BTC",),
                kwargs={"interval": "minute5", "count": count},
                max_attempts=2,
                base_delay=0.8,
                default=None,
            )
            if df is not None and not df.empty and "volume" in df.columns:
                vols = [_safe_float(v, 0.0) for v in list(df["volume"]) if _safe_float(v, 0.0) > 0]
                if vols:
                    return vols
        except Exception as exc:
            log.warn("pyupbit intraday volume fetch failed", error=exc)

    return []


def estimate_volume_profile(
    symbol: str,
    market: str,
    buckets: int,
    lookback_days: int = 5,
    supabase_client=None,
) -> List[float]:
    vols = _fetch_intraday_volume_series(
        symbol=symbol,
        market=market,
        lookback_days=lookback_days,
        supabase_client=supabase_client,
    )
    if not vols:
        return _default_u_curve(buckets)

    bucketed = _bucketize(vols, buckets)
    return _normalize_weights(bucketed, fallback_n=buckets)


@dataclass
class VWAPOrder:
    symbol: str
    side: str
    total_qty: float
    duration_minutes: int
    market: str = "auto"
    price_hint: Optional[float] = None
    buckets: int = 12
    lookback_days: int = 5


def build_vwap_schedule(order: VWAPOrder, profile: Optional[List[float]] = None, supabase_client=None) -> dict:
    symbol = str(order.symbol or "").strip().upper()
    side = _normalize_side(order.side)
    qty = max(_safe_float(order.total_qty), 0.0)
    duration_minutes = max(int(order.duration_minutes), 1)
    market = _infer_market(symbol, order.market)
    buckets = max(1, min(int(order.buckets), 240))

    # KR equity is share-based. Keep quantity integer to avoid overfill.
    if market == "kr":
        qty = float(max(int(round(qty)), 0))

    if qty <= 0:
        return {
            "symbol": symbol,
            "side": side,
            "market": market,
            "duration_minutes": duration_minutes,
            "total_qty": 0.0,
            "weights": [],
            "buckets": [],
        }

    weights = profile or estimate_volume_profile(
        symbol=symbol,
        market=market,
        buckets=buckets,
        lookback_days=order.lookback_days,
        supabase_client=supabase_client,
    )
    weights = _normalize_weights(weights, fallback_n=buckets)

    if len(weights) != buckets:
        # align profile length with bucket count
        if len(weights) < buckets:
            pad = _default_u_curve(buckets - len(weights))
            weights = _normalize_weights(weights + pad, fallback_n=buckets)
        else:
            weights = _normalize_weights(weights[:buckets], fallback_n=buckets)

    if market == "kr":
        total_shares = int(qty)
        if total_shares <= 0:
            return {
                "symbol": symbol,
                "side": side,
                "market": market,
                "duration_minutes": duration_minutes,
                "total_qty": 0.0,
                "weights": [],
                "buckets": [],
            }
        buckets = min(buckets, total_shares)
        if len(weights) != buckets:
            weights = _normalize_weights(weights[:buckets], fallback_n=buckets)

    duration_sec = duration_minutes * 60
    if buckets == 1:
        delays = [0]
    else:
        step = duration_sec / (buckets - 1)
        delays = [int(round(i * step)) for i in range(buckets)]

    out_buckets: List[dict] = []
    if market == "kr":
        total_shares = int(qty)
        desired = [qty * w for w in weights]
        share_alloc = [int(x) for x in desired]
        assigned = sum(share_alloc)
        remain = total_shares - assigned

        if remain > 0:
            frac_rank = sorted(
                [(idx, desired[idx] - share_alloc[idx]) for idx in range(len(share_alloc))],
                key=lambda t: t[1],
                reverse=True,
            )
            for idx, _ in frac_rank[:remain]:
                share_alloc[idx] += 1

        for i in range(buckets):
            out_buckets.append(
                {
                    "index": i + 1,
                    "delay_sec": int(delays[i]),
                    "weight": round(weights[i], 8),
                    "qty": float(max(0, share_alloc[i])),
                }
            )
    else:
        assigned = 0.0
        for i in range(buckets):
            if i == buckets - 1:
                leg_qty = max(0.0, qty - assigned)
            else:
                leg_qty = round(qty * weights[i], 8)
                assigned += leg_qty

            out_buckets.append(
                {
                    "index": i + 1,
                    "delay_sec": int(delays[i]),
                    "weight": round(weights[i], 8),
                    "qty": round(leg_qty, 8),
                }
            )

    return {
        "symbol": symbol,
        "side": side,
        "market": market,
        "duration_minutes": duration_minutes,
        "total_qty": round(qty, 8),
        "weights": [round(w, 8) for w in weights],
        "buckets": out_buckets,
    }


class VWAPExecutor:
    def __init__(self, sleep_fn: Callable[[float], None] = time.sleep):
        self.sleep_fn = sleep_fn

    def _native_place(self, payload: dict, upbit=None, kiwoom_client=None) -> dict:
        market = _infer_market(payload.get("symbol", ""), payload.get("market", "auto"))
        side = _normalize_side(payload.get("side", "buy"))
        qty = max(_safe_float(payload.get("qty"), 0.0), 0.0)
        symbol = str(payload.get("symbol", "")).upper()

        if qty <= 0:
            return {"result": "INVALID_QTY"}

        if market == "btc":
            if upbit is None:
                return {"result": "NO_CLIENT", "market": "btc"}

            market_code = symbol if symbol.startswith("KRW-") else ("KRW-BTC" if symbol == "BTC" else f"KRW-{symbol}")
            if side == "buy":
                px = _safe_float(payload.get("price_hint"), 0.0)
                if px <= 0:
                    px = _safe_float(get_price_snapshot(market_code, market="btc").get("price"), 0.0)
                notional = max(px * qty, 0.0)
                if notional <= 0:
                    return {"result": "INVALID_NOTIONAL", "market_code": market_code}
                return upbit.buy_market_order(market_code, notional)
            return upbit.sell_market_order(market_code, qty)

        if market == "kr":
            if kiwoom_client is None:
                return {"result": "NO_CLIENT", "market": "kr"}
            quantity = int(round(qty))
            if quantity <= 0:
                return {"result": "INVALID_QTY", "market": "kr"}
            return kiwoom_client.place_order(
                stock_code=symbol.lstrip("A"),
                order_type=side,
                quantity=quantity,
                price=0,
            )

        return {"result": "NO_CLIENT", "market": "us", "note": "provide place_order_fn"}

    def execute(
        self,
        order: VWAPOrder,
        place_order_fn: Optional[Callable[[dict], dict]] = None,
        upbit=None,
        kiwoom_client=None,
        simulate: bool = True,
        respect_schedule: bool = False,
        profile: Optional[List[float]] = None,
    ) -> dict:
        schedule = build_vwap_schedule(order, profile=profile)
        buckets = schedule.get("buckets") or []
        start_ts = time.time()
        fills: List[dict] = []

        for leg in buckets:
            target_delay = int(leg.get("delay_sec", 0))
            if respect_schedule:
                elapsed = time.time() - start_ts
                wait_for = target_delay - elapsed
                if wait_for > 0:
                    self.sleep_fn(wait_for)

            payload = {
                "symbol": schedule.get("symbol"),
                "side": schedule.get("side"),
                "market": schedule.get("market"),
                "qty": _safe_float(leg.get("qty"), 0.0),
                "price_hint": _safe_float(order.price_hint, 0.0),
            }

            if simulate and place_order_fn is None and upbit is None and kiwoom_client is None:
                response = {"result": "SIMULATED", "filled_qty": payload["qty"]}
            else:
                try:
                    if place_order_fn is not None:
                        response = place_order_fn(payload)
                    else:
                        response = self._native_place(payload, upbit=upbit, kiwoom_client=kiwoom_client)
                except Exception as exc:
                    response = {"result": "ERROR", "error": str(exc)}

            fills.append(
                {
                    "index": leg.get("index"),
                    "weight": leg.get("weight"),
                    "requested_qty": payload["qty"],
                    "timestamp": _utc_now_iso(),
                    "response": response,
                }
            )

        requested_qty = sum(_safe_float(x.get("requested_qty"), 0.0) for x in fills)
        return {
            "ok": True,
            "route": "VWAP",
            "schedule": schedule,
            "requested_qty": round(requested_qty, 8),
            "fill_count": len(fills),
            "fills": fills,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="VWAP execution helper")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", required=True, choices=["buy", "sell"])
    parser.add_argument("--total-qty", type=float, required=True)
    parser.add_argument("--duration", type=int, default=60, help="duration in minutes")
    parser.add_argument("--market", default="auto", choices=["auto", "btc", "kr", "us"])
    parser.add_argument("--price-hint", type=float, default=0.0)
    parser.add_argument("--buckets", type=int, default=12)
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--execute", action="store_true", help="simulate=false")
    parser.add_argument("--respect-schedule", action="store_true")
    args = parser.parse_args()

    order = VWAPOrder(
        symbol=args.symbol,
        side=args.side,
        total_qty=args.total_qty,
        duration_minutes=args.duration,
        market=args.market,
        price_hint=args.price_hint,
        buckets=args.buckets,
        lookback_days=args.lookback_days,
    )

    executor = VWAPExecutor()
    out = executor.execute(order, simulate=not args.execute, respect_schedule=args.respect_schedule)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
