"""Orderbook snapshot and stream helpers for Phase 9.

This module provides normalized orderbook data:
{
  bids: [{price, qty}],
  asks: [{price, qty}],
  spread,
  imbalance,
  timestamp,
}
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import requests

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("orderbook_data")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_get(url: str, *, params: Optional[dict] = None, timeout: int = 5):
    return retry_call(
        requests.get,
        args=(url,),
        kwargs={"params": params, "timeout": timeout},
        max_attempts=3,
        base_delay=0.5,
        default=None,
    )


def _normalize_levels(levels: List[list], top_n: int = 20) -> List[dict]:
    result: List[dict] = []
    for row in levels[:top_n]:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            price = float(row[0])
            qty = float(row[1])
        except Exception:
            continue
        if price <= 0 or qty < 0:
            continue
        result.append({"price": price, "qty": qty})
    return result


def calc_imbalance(bids: List[dict], asks: List[dict]) -> float:
    """(bid_vol - ask_vol) / (bid_vol + ask_vol)."""
    bid_vol = sum(max(float(x.get("qty", 0.0)), 0.0) for x in bids)
    ask_vol = sum(max(float(x.get("qty", 0.0)), 0.0) for x in asks)
    den = bid_vol + ask_vol
    if den <= 0:
        return 0.0
    return round((bid_vol - ask_vol) / den, 4)


def fetch_binance_orderbook(symbol: str = "BTCUSDT", limit: int = 20) -> Dict:
    """Fetch Binance spot depth snapshot."""
    cache_key = f"orderbook:binance:{symbol}:{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    res = _request_get(
        "https://api.binance.com/api/v3/depth",
        params={"symbol": symbol.upper(), "limit": min(max(limit, 5), 100)},
    )
    if res is None or not res.ok:
        log.warn("binance orderbook request failed", symbol=symbol)
        return {
            "symbol": symbol.upper(),
            "bids": [],
            "asks": [],
            "spread": 0.0,
            "imbalance": 0.0,
            "timestamp": _utc_now_iso(),
            "source": "binance",
        }

    try:
        data = res.json() or {}
        bids = _normalize_levels(data.get("bids", []), top_n=limit)
        asks = _normalize_levels(data.get("asks", []), top_n=limit)
    except Exception as exc:
        log.error("binance orderbook parse failed", error=exc)
        return {
            "symbol": symbol.upper(),
            "bids": [],
            "asks": [],
            "spread": 0.0,
            "imbalance": 0.0,
            "timestamp": _utc_now_iso(),
            "source": "binance",
        }

    best_bid = bids[0]["price"] if bids else 0.0
    best_ask = asks[0]["price"] if asks else 0.0
    spread = round(best_ask - best_bid, 6) if best_bid > 0 and best_ask > 0 else 0.0

    out = {
        "symbol": symbol.upper(),
        "bids": bids,
        "asks": asks,
        "spread": spread,
        "imbalance": calc_imbalance(bids, asks),
        "timestamp": _utc_now_iso(),
        "source": "binance",
    }
    set_cached(cache_key, out, ttl=2)
    return out


def fetch_upbit_orderbook(market: str = "KRW-BTC") -> Dict:
    """Fetch Upbit orderbook snapshot."""
    cache_key = f"orderbook:upbit:{market}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    res = _request_get("https://api.upbit.com/v1/orderbook", params={"markets": market})
    if res is None or not res.ok:
        log.warn("upbit orderbook request failed", market=market)
        return {
            "symbol": market,
            "bids": [],
            "asks": [],
            "spread": 0.0,
            "imbalance": 0.0,
            "timestamp": _utc_now_iso(),
            "source": "upbit",
        }

    try:
        rows = res.json() or []
        row = rows[0] if rows else {}
        units = row.get("orderbook_units", [])
        bids = [{"price": float(u.get("bid_price", 0.0)), "qty": float(u.get("bid_size", 0.0))} for u in units]
        asks = [{"price": float(u.get("ask_price", 0.0)), "qty": float(u.get("ask_size", 0.0))} for u in units]
    except Exception as exc:
        log.error("upbit orderbook parse failed", error=exc)
        return {
            "symbol": market,
            "bids": [],
            "asks": [],
            "spread": 0.0,
            "imbalance": 0.0,
            "timestamp": _utc_now_iso(),
            "source": "upbit",
        }

    best_bid = bids[0]["price"] if bids else 0.0
    best_ask = asks[0]["price"] if asks else 0.0
    spread = round(best_ask - best_bid, 6) if best_bid > 0 and best_ask > 0 else 0.0

    out = {
        "symbol": market,
        "bids": bids,
        "asks": asks,
        "spread": spread,
        "imbalance": calc_imbalance(bids, asks),
        "timestamp": _utc_now_iso(),
        "source": "upbit",
    }
    set_cached(cache_key, out, ttl=2)
    return out


def fetch_kr_orderbook_snapshot(stock_code: str, kiwoom_client=None) -> Dict:
    """Fetch KR orderbook snapshot.

    Kiwoom REST client currently does not expose a dedicated orderbook endpoint in
    this codebase, so this returns a synthetic 1-level snapshot around current
    price as fallback.
    """
    code = stock_code.lstrip("A")
    price = 0.0

    if kiwoom_client is not None:
        try:
            price = float(kiwoom_client.get_current_price(code) or 0.0)
        except Exception as exc:
            log.warn("kiwoom current price fetch failed", code=code, error=exc)

    if price <= 0:
        return {
            "symbol": code,
            "bids": [],
            "asks": [],
            "spread": 0.0,
            "imbalance": 0.0,
            "timestamp": _utc_now_iso(),
            "source": "kiwoom_fallback",
        }

    tick = max(round(price * 0.001, 0), 1.0)
    bids = [{"price": price - tick, "qty": 0.0}]
    asks = [{"price": price + tick, "qty": 0.0}]

    return {
        "symbol": code,
        "bids": bids,
        "asks": asks,
        "spread": round((price + tick) - (price - tick), 6),
        "imbalance": calc_imbalance(bids, asks),
        "timestamp": _utc_now_iso(),
        "source": "kiwoom_fallback",
    }


class BinanceOrderbookStream:
    """Polling stream interface for Binance orderbook snapshots."""

    def __init__(self, symbol: str = "BTCUSDT", poll_interval: float = 1.0, limit: int = 20):
        self.symbol = symbol.upper()
        self.poll_interval = max(0.25, poll_interval)
        self.limit = limit
        self._callbacks: List[Callable[[Dict], None]] = []
        self._stop = threading.Event()

    def on_snapshot(self, callback: Callable[[Dict], None]) -> None:
        self._callbacks.append(callback)

    def stop(self) -> None:
        self._stop.set()

    def pump_once(self) -> Dict:
        snap = fetch_binance_orderbook(symbol=self.symbol, limit=self.limit)
        for cb in self._callbacks:
            try:
                cb(snap)
            except Exception as exc:
                log.error("orderbook callback failed", error=exc)
        return snap

    def run_forever(self) -> None:
        log.info("orderbook stream started", symbol=self.symbol, poll_interval=self.poll_interval)
        while not self._stop.is_set():
            try:
                self.pump_once()
            except Exception as exc:
                log.error("orderbook stream loop failed", error=exc)
            self._stop.wait(self.poll_interval)


if __name__ == "__main__":
    stream = BinanceOrderbookStream(symbol="BTCUSDT", poll_interval=1.0)

    def _printer(snapshot: Dict):
        log.info(
            "orderbook",
            symbol=snapshot.get("symbol"),
            spread=snapshot.get("spread"),
            imbalance=snapshot.get("imbalance"),
        )

    stream.on_snapshot(_printer)
    try:
        stream.run_forever()
    except KeyboardInterrupt:
        stream.stop()
        log.info("orderbook stream stopped")
