"""Smart order router (Phase 13).

Routing policy:
- Size-based: small -> MARKET, medium -> TWAP, large -> VWAP
- Spread-based: narrow spread -> MARKET order type, wide spread -> LIMIT order type
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

from common.data.orderbook import (
    fetch_binance_orderbook,
    fetch_kr_orderbook_snapshot,
    fetch_upbit_orderbook,
)
from common.data.realtime_price import get_price_snapshot
from common.env_loader import load_env
from common.logger import get_logger
from execution.slippage_tracker import ExecutionFill, SlippageTracker
from execution.twap import TWAPExecutor, TWAPOrder
from execution.vwap import VWAPExecutor, VWAPOrder

load_env()
log = get_logger("smart_router")


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


def _extract_best_bid_ask(snapshot: dict) -> tuple[float, float, float]:
    bids = snapshot.get("bids") or []
    asks = snapshot.get("asks") or []
    best_bid = _safe_float(bids[0].get("price"), 0.0) if bids else 0.0
    best_ask = _safe_float(asks[0].get("price"), 0.0) if asks else 0.0
    spread = _safe_float(snapshot.get("spread"), 0.0)
    if spread <= 0 and best_bid > 0 and best_ask > 0:
        spread = max(best_ask - best_bid, 0.0)
    return best_bid, best_ask, spread


@dataclass
class RouterConfig:
    small_notional_threshold_krw: float = 1_000_000.0
    medium_notional_threshold_krw: float = 5_000_000.0
    small_notional_threshold_usd: float = 1_000.0
    medium_notional_threshold_usd: float = 5_000.0

    narrow_spread_bps: float = 8.0
    wide_spread_bps: float = 25.0

    twap_duration_minutes: int = 30
    vwap_duration_minutes: int = 90
    vwap_buckets: int = 12
    vwap_lookback_days: int = 5

    track_slippage: bool = True
    persist_slippage_to_db: bool = True
    respect_schedule: bool = False


@dataclass
class RouteDecision:
    symbol: str
    side: str
    market: str
    total_qty: float
    reference_price: float
    notional: float
    spread_bps: float
    route: str
    order_type: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class SmartRouter:
    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        twap_executor: Optional[TWAPExecutor] = None,
        vwap_executor: Optional[VWAPExecutor] = None,
        slippage_tracker: Optional[SlippageTracker] = None,
    ):
        self.config = config or RouterConfig()
        self.twap = twap_executor or TWAPExecutor()
        self.vwap = vwap_executor or VWAPExecutor()
        if slippage_tracker is not None:
            self.slippage_tracker = slippage_tracker
        elif self.config.track_slippage:
            self.slippage_tracker = SlippageTracker()
        else:
            self.slippage_tracker = SlippageTracker(supabase_client=None)

    def _thresholds(self, market: str) -> tuple[float, float]:
        if market in {"kr", "btc"}:
            return (
                _safe_float(self.config.small_notional_threshold_krw, 1_000_000.0),
                _safe_float(self.config.medium_notional_threshold_krw, 5_000_000.0),
            )
        return (
            _safe_float(self.config.small_notional_threshold_usd, 1_000.0),
            _safe_float(self.config.medium_notional_threshold_usd, 5_000.0),
        )

    def _get_spread_bps(self, symbol: str, market: str, kiwoom_client=None) -> float:
        mk = _infer_market(symbol, market)
        sym = str(symbol or "").upper()

        try:
            if mk == "btc":
                if sym.startswith("KRW-") or sym == "BTC":
                    snap = fetch_upbit_orderbook(sym if sym.startswith("KRW-") else "KRW-BTC")
                else:
                    pair = sym if sym.endswith("USDT") else "BTCUSDT"
                    snap = fetch_binance_orderbook(pair)
            elif mk == "kr":
                snap = fetch_kr_orderbook_snapshot(sym, kiwoom_client=kiwoom_client)
            else:
                # US fallback (no dedicated orderbook provider in current stack)
                return 15.0

            bid, ask, spread = _extract_best_bid_ask(snap)
            mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else 0.0
            if mid <= 0 or spread <= 0:
                return 15.0
            return max(0.0, (spread / mid) * 10000.0)
        except Exception as exc:
            log.warn("spread fetch failed", symbol=sym, market=mk, error=exc)
            return 15.0

    def _get_reference_price(self, symbol: str, market: str, price_hint: Optional[float], kiwoom_client=None) -> float:
        if _safe_float(price_hint, 0.0) > 0:
            return _safe_float(price_hint, 0.0)
        try:
            snap = get_price_snapshot(symbol, market=market, kiwoom_client=kiwoom_client)
            return _safe_float(snap.get("price"), 0.0)
        except Exception:
            return 0.0

    def decide(
        self,
        symbol: str,
        side: str,
        total_qty: float,
        market: str = "auto",
        price_hint: Optional[float] = None,
        kiwoom_client=None,
    ) -> RouteDecision:
        sym = str(symbol or "").upper().strip()
        sd = _normalize_side(side)
        mk = _infer_market(sym, market)
        qty = max(_safe_float(total_qty, 0.0), 0.0)

        ref_price = self._get_reference_price(sym, mk, price_hint, kiwoom_client=kiwoom_client)
        notional = qty * ref_price if ref_price > 0 else 0.0

        small, medium = self._thresholds(mk)
        if notional <= small:
            route = "MARKET"
            reason = f"small_notional <= {small}"
        elif notional <= medium:
            route = "TWAP"
            reason = f"medium_notional <= {medium}"
        else:
            route = "VWAP"
            reason = f"large_notional > {medium}"

        spread_bps = self._get_spread_bps(sym, mk, kiwoom_client=kiwoom_client)
        order_type = "MARKET" if spread_bps <= self.config.narrow_spread_bps else "LIMIT"

        if route == "MARKET" and spread_bps >= self.config.wide_spread_bps:
            route = "TWAP"
            reason += f" + wide_spread({spread_bps:.2f}bps)"
        elif route == "TWAP" and spread_bps >= self.config.wide_spread_bps * 1.6:
            route = "VWAP"
            reason += f" + very_wide_spread({spread_bps:.2f}bps)"

        return RouteDecision(
            symbol=sym,
            side=sd,
            market=mk,
            total_qty=round(qty, 8),
            reference_price=round(ref_price, 8),
            notional=round(notional, 8),
            spread_bps=round(spread_bps, 6),
            route=route,
            order_type=order_type,
            reason=reason,
        )

    def _extract_actual_price(self, response: dict, fallback_price: float) -> float:
        if not isinstance(response, dict):
            return fallback_price

        for k in ("avg_price", "avg_buy_price", "avg_sell_price", "executed_price", "trade_price", "price"):
            v = _safe_float(response.get(k), 0.0)
            if v > 0:
                return v

        trades = response.get("trades")
        if isinstance(trades, list) and trades:
            weighted = 0.0
            qty_sum = 0.0
            for t in trades:
                if not isinstance(t, dict):
                    continue
                p = _safe_float(t.get("price"), 0.0)
                q = _safe_float(t.get("qty") or t.get("volume"), 0.0)
                if p > 0 and q > 0:
                    weighted += p * q
                    qty_sum += q
            if qty_sum > 0:
                return weighted / qty_sum

        return fallback_price

    def _track_result(self, decision: RouteDecision, execution_result: dict, persist_db: bool) -> dict:
        fills = execution_result.get("fills") or []
        rows: List[dict] = []

        for f in fills:
            req_qty = max(_safe_float(f.get("requested_qty"), 0.0), 0.0)
            if req_qty <= 0:
                continue

            response = f.get("response") or {}
            actual = self._extract_actual_price(response, decision.reference_price)
            expected = decision.reference_price
            if expected <= 0 or actual <= 0:
                continue

            fill = ExecutionFill(
                symbol=decision.symbol,
                side=decision.side,
                qty=req_qty,
                expected_price=expected,
                actual_price=actual,
                market=decision.market,
                route=decision.route,
                order_type=decision.order_type,
                timestamp=str(f.get("timestamp") or ""),
                metadata={
                    "response": response,
                    "fill_index": f.get("index"),
                },
            )
            row = self.slippage_tracker.track_fill(fill, persist_db=persist_db)
            rows.append(row)

        if not rows:
            return {"tracked": 0, "avg_abs_slippage_bps": 0.0, "avg_adverse_slippage_bps": 0.0}

        abs_vals = [_safe_float(r.get("abs_slippage_bps"), 0.0) for r in rows]
        adv_vals = [_safe_float(r.get("adverse_slippage_bps"), 0.0) for r in rows]
        return {
            "tracked": len(rows),
            "avg_abs_slippage_bps": round(sum(abs_vals) / len(abs_vals), 6),
            "avg_adverse_slippage_bps": round(sum(adv_vals) / len(adv_vals), 6),
        }

    def route_order(
        self,
        symbol: str,
        side: str,
        total_qty: float,
        market: str = "auto",
        price_hint: Optional[float] = None,
        place_order_fn: Optional[Callable[[dict], dict]] = None,
        upbit=None,
        kiwoom_client=None,
        simulate: bool = True,
        respect_schedule: Optional[bool] = None,
        vwap_profile: Optional[List[float]] = None,
    ) -> dict:
        decision = self.decide(
            symbol=symbol,
            side=side,
            total_qty=total_qty,
            market=market,
            price_hint=price_hint,
            kiwoom_client=kiwoom_client,
        )

        use_schedule = self.config.respect_schedule if respect_schedule is None else bool(respect_schedule)

        if decision.route == "MARKET":
            payload = {
                "symbol": decision.symbol,
                "side": decision.side,
                "market": decision.market,
                "qty": decision.total_qty,
                "price_hint": decision.reference_price,
            }
            if simulate and place_order_fn is None and upbit is None and kiwoom_client is None:
                response = {"result": "SIMULATED", "filled_qty": decision.total_qty}
            else:
                try:
                    if place_order_fn is not None:
                        response = place_order_fn(payload)
                    else:
                        response = self.twap._native_place(payload, upbit=upbit, kiwoom_client=kiwoom_client)
                except Exception as exc:
                    response = {"result": "ERROR", "error": str(exc)}

            exec_result = {
                "ok": True,
                "route": "MARKET",
                "schedule": {
                    "symbol": decision.symbol,
                    "side": decision.side,
                    "market": decision.market,
                    "duration_minutes": 0,
                    "total_qty": decision.total_qty,
                    "slices": [{"index": 1, "delay_sec": 0, "qty": decision.total_qty}],
                },
                "requested_qty": decision.total_qty,
                "fill_count": 1,
                "fills": [
                    {
                        "index": 1,
                        "requested_qty": decision.total_qty,
                        "timestamp": _utc_now_iso(),
                        "response": response,
                    }
                ],
            }
        elif decision.route == "TWAP":
            twap_order = TWAPOrder(
                symbol=decision.symbol,
                side=decision.side,
                total_qty=decision.total_qty,
                duration_minutes=self.config.twap_duration_minutes,
                market=decision.market,
                price_hint=decision.reference_price,
            )
            exec_result = self.twap.execute(
                twap_order,
                place_order_fn=place_order_fn,
                upbit=upbit,
                kiwoom_client=kiwoom_client,
                simulate=simulate,
                respect_schedule=use_schedule,
            )
        else:
            vwap_order = VWAPOrder(
                symbol=decision.symbol,
                side=decision.side,
                total_qty=decision.total_qty,
                duration_minutes=self.config.vwap_duration_minutes,
                market=decision.market,
                price_hint=decision.reference_price,
                buckets=self.config.vwap_buckets,
                lookback_days=self.config.vwap_lookback_days,
            )
            exec_result = self.vwap.execute(
                vwap_order,
                place_order_fn=place_order_fn,
                upbit=upbit,
                kiwoom_client=kiwoom_client,
                simulate=simulate,
                respect_schedule=use_schedule,
                profile=vwap_profile,
            )

        if self.config.track_slippage:
            persist = self.config.persist_slippage_to_db and (not simulate)
            slippage = self._track_result(decision, exec_result, persist_db=persist)
        else:
            slippage = {"tracked": 0, "avg_abs_slippage_bps": 0.0, "avg_adverse_slippage_bps": 0.0}

        return {
            "ok": True,
            "decision": decision.to_dict(),
            "execution": exec_result,
            "slippage": slippage,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Smart order router")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", required=True, choices=["buy", "sell"])
    parser.add_argument("--qty", type=float, required=True)
    parser.add_argument("--market", default="auto", choices=["auto", "btc", "kr", "us"])
    parser.add_argument("--price-hint", type=float, default=0.0)
    parser.add_argument("--execute", action="store_true", help="run non-simulated execution")
    parser.add_argument("--route-only", action="store_true")
    args = parser.parse_args()

    router = SmartRouter()
    if args.route_only:
        decision = router.decide(
            symbol=args.symbol,
            side=args.side,
            total_qty=args.qty,
            market=args.market,
            price_hint=args.price_hint,
        )
        print(json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))
        return 0

    out = router.route_order(
        symbol=args.symbol,
        side=args.side,
        total_qty=args.qty,
        market=args.market,
        price_hint=args.price_hint,
        simulate=not args.execute,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
