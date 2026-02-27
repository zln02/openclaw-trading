"""US broker adapter with Alpaca support (Phase 16)."""
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
from execution.smart_router import RouterConfig, SmartRouter

load_env()
log = get_logger("us_broker")

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://api.alpaca.markets"


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
class BrokerOrderResult:
    ok: bool
    mode: str
    broker: str
    status: str
    symbol: str
    side: str
    qty: float
    order_type: str
    order_id: str
    raw: dict
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class AlpacaBroker:
    def __init__(
        self,
        live: bool = False,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        router: Optional[SmartRouter] = None,
    ):
        self.live = bool(live)
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY", "")

        configured_url = os.environ.get("ALPACA_BASE_URL", "")
        self.base_url = base_url or configured_url or (LIVE_BASE_URL if self.live else PAPER_BASE_URL)

        self.router = router or SmartRouter(
            config=RouterConfig(
                small_notional_threshold_usd=1000.0,
                medium_notional_threshold_usd=5000.0,
                track_slippage=False,
            )
        )

    @property
    def mode(self) -> str:
        return "live" if self.live else "paper"

    @property
    def credentials_ready(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def _headers(self) -> dict:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        if not self.credentials_ready:
            return {"ok": False, "error": "missing_credentials"}

        url = f"{self.base_url}{path}"
        resp = retry_call(
            requests.request,
            args=(method, url),
            kwargs={
                "headers": self._headers(),
                "json": payload,
                "timeout": 10,
            },
            max_attempts=3,
            base_delay=0.7,
            default=None,
        )
        if resp is None:
            return {"ok": False, "error": "request_failed"}

        try:
            data = resp.json() if resp.content else {}
        except Exception:
            data = {"text": getattr(resp, "text", "")}

        return {
            "ok": bool(resp.ok),
            "status_code": getattr(resp, "status_code", 0),
            "data": data,
        }

    def get_account(self) -> dict:
        if not self.credentials_ready:
            return {
                "ok": True,
                "mode": self.mode,
                "simulated": True,
                "account_status": "SIMULATED",
                "timestamp": _utc_now_iso(),
            }

        out = self._request("GET", "/v2/account")
        return {
            "ok": bool(out.get("ok")),
            "mode": self.mode,
            "simulated": False,
            "account": out.get("data") or {},
            "timestamp": _utc_now_iso(),
        }

    def submit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        time_in_force: str = "day",
        simulate: bool = False,
    ) -> dict:
        sym = str(symbol or "").upper()
        sd = str(side or "").lower()
        q = max(_safe_float(qty, 0.0), 0.0)
        order_t = str(order_type or "market").lower()

        if q <= 0 or sd not in {"buy", "sell"}:
            return BrokerOrderResult(
                ok=False,
                mode=self.mode,
                broker="alpaca",
                status="REJECTED",
                symbol=sym,
                side=sd,
                qty=q,
                order_type=order_t,
                order_id="",
                raw={"error": "invalid_order_params"},
                timestamp=_utc_now_iso(),
            ).to_dict()

        if simulate or (not self.credentials_ready):
            return BrokerOrderResult(
                ok=True,
                mode=self.mode,
                broker="alpaca",
                status="SIMULATED",
                symbol=sym,
                side=sd,
                qty=round(q, 8),
                order_type=order_t,
                order_id=f"sim-{int(datetime.now().timestamp())}",
                raw={
                    "symbol": sym,
                    "side": sd,
                    "qty": q,
                    "type": order_t,
                    "limit_price": limit_price,
                    "time_in_force": time_in_force,
                },
                timestamp=_utc_now_iso(),
            ).to_dict()

        payload = {
            "symbol": sym,
            "side": sd,
            "qty": str(round(q, 8)),
            "type": order_t,
            "time_in_force": time_in_force,
        }
        if order_t == "limit" and _safe_float(limit_price, 0.0) > 0:
            payload["limit_price"] = str(round(_safe_float(limit_price, 0.0), 6))

        out = self._request("POST", "/v2/orders", payload=payload)
        data = out.get("data") or {}

        return BrokerOrderResult(
            ok=bool(out.get("ok")),
            mode=self.mode,
            broker="alpaca",
            status=str(data.get("status") or ("ACCEPTED" if out.get("ok") else "ERROR")),
            symbol=sym,
            side=sd,
            qty=round(q, 8),
            order_type=order_t,
            order_id=str(data.get("id") or ""),
            raw=data if isinstance(data, dict) else {"data": data},
            timestamp=_utc_now_iso(),
        ).to_dict()

    def _place_router_payload(self, payload: dict, simulate: bool) -> dict:
        symbol = str(payload.get("symbol") or "").upper()
        side = str(payload.get("side") or "buy").lower()
        qty = _safe_float(payload.get("qty"), 0.0)
        price_hint = _safe_float(payload.get("price_hint"), 0.0)

        order_type = str(payload.get("order_type") or "market").lower()
        limit_price = price_hint if order_type == "limit" and price_hint > 0 else None

        return self.submit_order(
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            simulate=simulate,
        )

    def route_and_execute(
        self,
        symbol: str,
        side: str,
        qty: float,
        price_hint: Optional[float] = None,
        simulate: bool = True,
    ) -> dict:
        use_sim = bool(simulate or (not self.credentials_ready))

        out = self.router.route_order(
            symbol=symbol,
            side=side,
            total_qty=qty,
            market="us",
            price_hint=price_hint,
            place_order_fn=lambda p: self._place_router_payload(p, simulate=use_sim),
            simulate=use_sim,
            respect_schedule=False,
        )
        out["broker_mode"] = self.mode
        out["credentials_ready"] = self.credentials_ready
        return out


def _cli() -> int:
    parser = argparse.ArgumentParser(description="US Alpaca broker adapter")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--side", default="buy", choices=["buy", "sell"])
    parser.add_argument("--qty", type=float, default=1.0)
    parser.add_argument("--price-hint", type=float, default=0.0)
    parser.add_argument("--live", action="store_true", help="switch to live trading endpoint")
    parser.add_argument("--execute", action="store_true", help="attempt real order submission")
    parser.add_argument("--account", action="store_true", help="query account only")
    args = parser.parse_args()

    broker = AlpacaBroker(live=args.live)

    if args.account:
        out = broker.get_account()
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    out = broker.route_and_execute(
        symbol=args.symbol,
        side=args.side,
        qty=args.qty,
        price_hint=(args.price_hint if args.price_hint > 0 else None),
        simulate=not args.execute,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
