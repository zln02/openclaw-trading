"""TWAP execution algorithm (Phase 13).

Input:
- { symbol, side, total_qty, duration_minutes }

Output:
- execution plan + fills
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from common.data.realtime_price import get_price_snapshot
from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("execution_twap")


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


def min_interval_seconds(market: str) -> int:
    mk = str(market or "").strip().lower()
    if mk == "kr":
        return 20  # Kiwoom REST 안정 구간
    if mk == "btc":
        return 3   # Upbit는 상대적으로 빠른 호출 가능
    return 5


@dataclass
class TWAPOrder:
    symbol: str
    side: str
    total_qty: float
    duration_minutes: int
    market: str = "auto"
    price_hint: Optional[float] = None


def build_twap_schedule(order: TWAPOrder) -> dict:
    symbol = str(order.symbol or "").strip().upper()
    side = _normalize_side(order.side)
    qty = max(_safe_float(order.total_qty), 0.0)
    duration_minutes = max(int(order.duration_minutes), 1)
    market = _infer_market(symbol, order.market)

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
            "slices": [],
        }

    duration_sec = duration_minutes * 60
    target_interval = {"btc": 10, "kr": 30, "us": 20}.get(market, 20)

    slices = max(1, int(round(duration_sec / target_interval)))
    minimum_interval = min_interval_seconds(market)

    if slices > 1:
        raw_interval = duration_sec / max(slices - 1, 1)
        if raw_interval < minimum_interval:
            slices = max(1, int(duration_sec // minimum_interval) + 1)

    slices = max(1, min(slices, 240))

    if market == "kr":
        total_shares = int(qty)
        if total_shares <= 0:
            return {
                "symbol": symbol,
                "side": side,
                "market": market,
                "duration_minutes": duration_minutes,
                "total_qty": 0.0,
                "slices": [],
            }
        slices = min(slices, total_shares)

    if slices == 1:
        delays = [0]
    else:
        step = duration_sec / (slices - 1)
        delays = [int(round(i * step)) for i in range(slices)]

    out_slices: List[dict] = []
    if market == "kr":
        total_shares = int(qty)
        base_shares = total_shares // slices
        remainder = total_shares % slices

        for i in range(slices):
            leg_qty = float(base_shares + (1 if i < remainder else 0))
            out_slices.append(
                {
                    "index": i + 1,
                    "delay_sec": int(delays[i]),
                    "qty": leg_qty,
                }
            )
    else:
        base_qty = qty / slices
        assigned = 0.0
        for i in range(slices):
            if i == slices - 1:
                leg_qty = max(0.0, qty - assigned)
            else:
                leg_qty = round(base_qty, 8)
                assigned += leg_qty

            out_slices.append(
                {
                    "index": i + 1,
                    "delay_sec": int(delays[i]),
                    "qty": round(leg_qty, 8),
                }
            )

    return {
        "symbol": symbol,
        "side": side,
        "market": market,
        "duration_minutes": duration_minutes,
        "total_qty": round(qty, 8),
        "slices": out_slices,
    }


class TWAPExecutor:
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

            market_code = symbol
            if not market_code.startswith("KRW-"):
                market_code = "KRW-BTC" if market_code == "BTC" else f"KRW-{market_code}"

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
            stock_code = symbol.lstrip("A")
            return kiwoom_client.place_order(
                stock_code=stock_code,
                order_type=side,
                quantity=quantity,
                price=0,
            )

        # US live order path is broker-dependent (Alpaca etc.)
        return {"result": "NO_CLIENT", "market": "us", "note": "provide place_order_fn"}

    def execute(
        self,
        order: TWAPOrder,
        place_order_fn: Optional[Callable[[dict], dict]] = None,
        upbit=None,
        kiwoom_client=None,
        simulate: bool = True,
        respect_schedule: bool = False,
    ) -> dict:
        schedule = build_twap_schedule(order)
        slices = schedule.get("slices") or []
        start_ts = time.time()
        fills: List[dict] = []

        for leg in slices:
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
                    "requested_qty": payload["qty"],
                    "timestamp": _utc_now_iso(),
                    "response": response,
                }
            )

        requested_qty = sum(_safe_float(x.get("requested_qty"), 0.0) for x in fills)
        return {
            "ok": True,
            "route": "TWAP",
            "schedule": schedule,
            "requested_qty": round(requested_qty, 8),
            "fill_count": len(fills),
            "fills": fills,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="TWAP execution helper")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", required=True, choices=["buy", "sell"])
    parser.add_argument("--total-qty", type=float, required=True)
    parser.add_argument("--duration", type=int, default=30, help="duration in minutes")
    parser.add_argument("--market", default="auto", choices=["auto", "btc", "kr", "us"])
    parser.add_argument("--price-hint", type=float, default=0.0)
    parser.add_argument("--execute", action="store_true", help="simulate=false")
    parser.add_argument("--respect-schedule", action="store_true")
    args = parser.parse_args()

    order = TWAPOrder(
        symbol=args.symbol,
        side=args.side,
        total_qty=args.total_qty,
        duration_minutes=args.duration,
        market=args.market,
        price_hint=args.price_hint,
    )
    executor = TWAPExecutor()
    out = executor.execute(
        order,
        simulate=not args.execute,
        respect_schedule=args.respect_schedule,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
