"""BTC exchange arbitrage detector (Phase 14).

Compare Upbit KRW-BTC vs Binance BTCUSDT in near real-time and compute
Kimchi premium.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from common.cache import get_cached, set_cached
from common.data.realtime_price import get_btc_price
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("btc_arb_detector")

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def compute_kimchi_premium(upbit_price_krw: float, binance_price_usdt: float, usd_krw: float) -> float:
    up = _safe_float(upbit_price_krw, 0.0)
    bn = _safe_float(binance_price_usdt, 0.0)
    fx = _safe_float(usd_krw, 0.0)
    if up <= 0 or bn <= 0 or fx <= 0:
        return 0.0
    fair_krw = bn * fx
    return round((up - fair_krw) / fair_krw * 100.0, 6)


@dataclass
class ArbitrageSignal:
    symbol: str
    upbit_price_krw: float
    binance_price_usdt: float
    usd_krw: float
    kimchi_premium_pct: float
    state: str
    signal_boost: float
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class ArbitrageDetector:
    def __init__(
        self,
        premium_alert_pct: float = 5.0,
        reverse_premium_pct: float = -1.0,
    ):
        self.premium_alert_pct = _safe_float(premium_alert_pct, 5.0)
        self.reverse_premium_pct = _safe_float(reverse_premium_pct, -1.0)

    def _fetch_binance_price(self, symbol: str = "BTCUSDT") -> float:
        sym = str(symbol or "BTCUSDT").upper()
        cache_key = f"arb:binance:{sym}"
        cached = get_cached(cache_key)
        if cached is not None:
            return _safe_float(cached, 0.0)

        resp = retry_call(
            requests.get,
            args=(BINANCE_TICKER_URL,),
            kwargs={"params": {"symbol": sym}, "timeout": 5},
            max_attempts=3,
            base_delay=0.5,
            default=None,
        )
        if resp is None or not getattr(resp, "ok", False):
            return 0.0

        try:
            price = _safe_float((resp.json() or {}).get("price"), 0.0)
            if price > 0:
                set_cached(cache_key, price, ttl=2)
            return price
        except Exception:
            return 0.0

    def _fetch_usd_krw(self) -> float:
        cache_key = "arb:usdkrw"
        cached = get_cached(cache_key)
        if cached is not None:
            return _safe_float(cached, 0.0)

        resp = retry_call(
            requests.get,
            args=(UPBIT_TICKER_URL,),
            kwargs={"params": {"markets": "KRW-USDT"}, "timeout": 5},
            max_attempts=3,
            base_delay=0.5,
            default=None,
        )
        if resp is None or not getattr(resp, "ok", False):
            return 0.0

        try:
            rows = resp.json() or []
            fx = _safe_float(rows[0].get("trade_price"), 0.0) if rows else 0.0
            if fx > 0:
                set_cached(cache_key, fx, ttl=3)
            return fx
        except Exception:
            return 0.0

    def detect(
        self,
        upbit_price_krw: Optional[float] = None,
        binance_price_usdt: Optional[float] = None,
        usd_krw: Optional[float] = None,
        symbol: str = "BTC",
    ) -> dict:
        up = _safe_float(upbit_price_krw, 0.0)
        if up <= 0:
            up = _safe_float(get_btc_price("KRW-BTC").get("price"), 0.0)

        bn = _safe_float(binance_price_usdt, 0.0)
        if bn <= 0:
            bn = self._fetch_binance_price("BTCUSDT")

        fx = _safe_float(usd_krw, 0.0)
        if fx <= 0:
            fx = self._fetch_usd_krw()

        premium = compute_kimchi_premium(up, bn, fx)
        if premium >= self.premium_alert_pct:
            state = "KIMCHI_PREMIUM_ALERT"
            signal_boost = -1.0
            reason = f"premium {premium:.2f}% >= {self.premium_alert_pct:.2f}%"
        elif premium <= self.reverse_premium_pct:
            state = "REVERSE_PREMIUM"
            signal_boost = 1.0
            reason = f"reverse premium {premium:.2f}% <= {self.reverse_premium_pct:.2f}%"
        else:
            state = "NORMAL"
            signal_boost = 0.0
            reason = "premium in neutral zone"

        out = ArbitrageSignal(
            symbol=str(symbol or "BTC").upper(),
            upbit_price_krw=round(up, 4),
            binance_price_usdt=round(bn, 6),
            usd_krw=round(fx, 6),
            kimchi_premium_pct=round(premium, 6),
            state=state,
            signal_boost=signal_boost,
            reason=reason,
            timestamp=_utc_now_iso(),
        )
        return out.to_dict()


def _cli() -> int:
    parser = argparse.ArgumentParser(description="BTC arbitrage detector")
    parser.add_argument("--upbit", type=float, default=0.0, help="override upbit KRW price")
    parser.add_argument("--binance", type=float, default=0.0, help="override binance USDT price")
    parser.add_argument("--usdkrw", type=float, default=0.0, help="override USDKRW")
    parser.add_argument("--alert", type=float, default=5.0)
    parser.add_argument("--reverse", type=float, default=-1.0)
    args = parser.parse_args()

    detector = ArbitrageDetector(premium_alert_pct=args.alert, reverse_premium_pct=args.reverse)
    out = detector.detect(
        upbit_price_krw=args.upbit,
        binance_price_usdt=args.binance,
        usd_krw=args.usdkrw,
        symbol="BTC",
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
