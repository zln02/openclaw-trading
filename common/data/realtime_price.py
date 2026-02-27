"""Realtime price helpers for Phase 9.

Normalized tick schema:
{
  symbol,
  price,
  volume,
  timestamp,
  source,
}
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("realtime_price")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_tick(symbol: str, source: str) -> Dict:
    return {
        "symbol": symbol,
        "price": 0.0,
        "volume": 0.0,
        "timestamp": _utc_now_iso(),
        "source": source,
    }


def get_btc_price(market: str = "KRW-BTC") -> Dict:
    """Get BTC price snapshot from Upbit, fallback to yfinance."""
    cache_key = f"tick:btc:{market}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    tick = _empty_tick(market, "upbit")

    try:
        import pyupbit

        price = retry_call(
            pyupbit.get_current_price,
            args=(market,),
            max_attempts=3,
            base_delay=0.5,
            default=None,
        )
        if price is not None:
            tick["price"] = float(price)
            set_cached(cache_key, tick, ttl=1)
            return tick
    except Exception as exc:
        log.warn("upbit price fetch failed", market=market, error=exc)

    try:
        import yfinance as yf

        hist = retry_call(
            yf.download,
            args=("BTC-USD",),
            kwargs={"period": "1d", "interval": "1m", "progress": False},
            max_attempts=2,
            base_delay=1.0,
            default=None,
        )
        if hist is not None and not hist.empty:
            tick.update(
                {
                    "price": float(hist["Close"].iloc[-1]),
                    "volume": float(hist["Volume"].iloc[-1] or 0.0),
                    "source": "yfinance",
                }
            )
    except Exception as exc:
        log.warn("yfinance btc fallback failed", error=exc)

    set_cached(cache_key, tick, ttl=2)
    return tick


def get_us_price(symbol: str) -> Dict:
    """Get US symbol snapshot using yfinance."""
    sym = symbol.upper()
    cache_key = f"tick:us:{sym}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    tick = _empty_tick(sym, "yfinance")

    try:
        import yfinance as yf

        t = yf.Ticker(sym)
        hist = retry_call(
            t.history,
            kwargs={"period": "1d", "interval": "1m"},
            max_attempts=2,
            base_delay=1.0,
            default=None,
        )
        if hist is not None and not hist.empty:
            tick["price"] = float(hist["Close"].iloc[-1])
            tick["volume"] = float(hist["Volume"].iloc[-1] or 0.0)
    except Exception as exc:
        log.warn("us price fetch failed", symbol=sym, error=exc)

    set_cached(cache_key, tick, ttl=2)
    return tick


def _to_yf_kr_symbol(code: str) -> str:
    raw = code.upper().lstrip("A")
    if raw.endswith(".KS") or raw.endswith(".KQ"):
        return raw
    # default to KOSPI suffix
    return f"{raw}.KS"


def get_kr_price(stock_code: str, kiwoom_client=None) -> Dict:
    """Get KR stock snapshot from Kiwoom client (preferred) or yfinance fallback."""
    code = stock_code.upper().lstrip("A")
    cache_key = f"tick:kr:{code}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    tick = _empty_tick(code, "kiwoom")

    if kiwoom_client is not None:
        try:
            price = float(kiwoom_client.get_current_price(code) or 0.0)
            if price > 0:
                tick["price"] = price
                set_cached(cache_key, tick, ttl=1)
                return tick
        except Exception as exc:
            log.warn("kiwoom price fetch failed", code=code, error=exc)

    try:
        import yfinance as yf

        sym = _to_yf_kr_symbol(code)
        t = yf.Ticker(sym)
        hist = retry_call(
            t.history,
            kwargs={"period": "1d", "interval": "1m"},
            max_attempts=2,
            base_delay=1.0,
            default=None,
        )
        if hist is not None and not hist.empty:
            tick.update(
                {
                    "symbol": sym,
                    "price": float(hist["Close"].iloc[-1]),
                    "volume": float(hist["Volume"].iloc[-1] or 0.0),
                    "source": "yfinance",
                }
            )
    except Exception as exc:
        log.warn("kr yfinance fallback failed", code=code, error=exc)

    set_cached(cache_key, tick, ttl=2)
    return tick


def get_price_snapshot(symbol: str, market: str = "auto", kiwoom_client=None) -> Dict:
    """Unified helper for BTC/KR/US symbols."""
    mk = market.lower().strip()
    if mk == "btc":
        return get_btc_price(symbol)
    if mk == "kr":
        return get_kr_price(symbol, kiwoom_client=kiwoom_client)
    if mk == "us":
        return get_us_price(symbol)

    upper = symbol.upper()
    if upper.startswith("KRW-") or upper.endswith("USDT") or upper == "BTC":
        m = "KRW-BTC" if upper == "BTC" else symbol
        return get_btc_price(m)
    if upper.isdigit() or upper.startswith("A"):
        return get_kr_price(symbol, kiwoom_client=kiwoom_client)
    return get_us_price(symbol)


class RealtimePriceFeed:
    """Polling price feed with callback registration."""

    def __init__(
        self,
        symbol: str,
        market: str = "auto",
        poll_interval: float = 1.0,
        kiwoom_client=None,
    ):
        self.symbol = symbol
        self.market = market
        self.poll_interval = max(0.25, poll_interval)
        self.kiwoom_client = kiwoom_client
        self._callbacks: list[Callable[[Dict], None]] = []
        self._stop = threading.Event()

    def on_tick(self, callback: Callable[[Dict], None]) -> None:
        self._callbacks.append(callback)

    def stop(self) -> None:
        self._stop.set()

    def pump_once(self) -> Dict:
        tick = get_price_snapshot(
            self.symbol,
            market=self.market,
            kiwoom_client=self.kiwoom_client,
        )
        for cb in self._callbacks:
            try:
                cb(tick)
            except Exception as exc:
                log.error("price callback failed", error=exc)
        return tick

    def run_forever(self) -> None:
        log.info(
            "price feed started",
            symbol=self.symbol,
            market=self.market,
            poll_interval=self.poll_interval,
        )
        while not self._stop.is_set():
            try:
                self.pump_once()
            except Exception as exc:
                log.error("price feed loop failed", error=exc)
            self._stop.wait(self.poll_interval)


if __name__ == "__main__":
    feed = RealtimePriceFeed("KRW-BTC", market="btc", poll_interval=1.0)

    def _printer(tick: Dict):
        log.info("tick", symbol=tick.get("symbol"), price=tick.get("price"), source=tick.get("source"))

    feed.on_tick(_printer)
    try:
        feed.run_forever()
    except KeyboardInterrupt:
        feed.stop()
        log.info("price feed stopped")
