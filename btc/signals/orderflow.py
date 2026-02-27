"""BTC orderflow analyzer (Phase 14).

Features:
- Binance trade stream consumption (WebSocket when available)
- CVD (Cumulative Volume Delta)
- Large trade count tracking (> configurable BTC threshold)
- Rolling net flow
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import requests

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("btc_orderflow")

BINANCE_TRADE_WS = "wss://fstream.binance.com/ws/{symbol}@trade"
BINANCE_RECENT_TRADES_URL = "https://fapi.binance.com/fapi/v1/trades"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_epoch_seconds(ts: Any) -> float:
    v = _safe_float(ts, 0.0)
    if v <= 0:
        return time.time()
    # Heuristic: Binance event timestamps are usually in ms.
    return v / 1000.0 if v > 10_000_000_000 else v


def _is_aggressive_sell(trade: dict) -> bool:
    if "m" in trade:
        return bool(trade.get("m"))
    if "is_buyer_maker" in trade:
        return bool(trade.get("is_buyer_maker"))

    side = str(trade.get("side") or "").strip().lower()
    if side in {"sell", "ask", "s"}:
        return True
    if side in {"buy", "bid", "b"}:
        return False
    return False


@dataclass
class OrderFlowState:
    cvd: float
    large_buy_count: int
    large_sell_count: int
    net_flow: float
    buy_volume: float
    sell_volume: float
    trade_count: int
    large_trade_threshold_btc: float
    window_seconds: int
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class OrderFlowAnalyzer:
    def __init__(self, large_trade_threshold_btc: float = 10.0, window_seconds: int = 300):
        self.large_trade_threshold_btc = max(_safe_float(large_trade_threshold_btc, 10.0), 0.01)
        self.window_seconds = max(int(window_seconds), 1)

        self._cvd = 0.0
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._large_buy_count = 0
        self._large_sell_count = 0
        self._trade_count = 0
        self._rolling: deque[tuple[float, float]] = deque()

    def _prune_rolling(self, now_ts: float) -> None:
        cutoff = now_ts - self.window_seconds
        while self._rolling and self._rolling[0][0] < cutoff:
            self._rolling.popleft()

    def process_trade(self, trade: dict) -> None:
        qty = _safe_float(
            trade.get("q", trade.get("qty", trade.get("quantity", trade.get("size")))),
            0.0,
        )
        if qty <= 0:
            return

        ts = _to_epoch_seconds(trade.get("T", trade.get("timestamp", trade.get("ts"))))
        is_sell = _is_aggressive_sell(trade)
        signed_qty = -qty if is_sell else qty

        self._cvd += signed_qty
        self._trade_count += 1

        if signed_qty >= 0:
            self._buy_volume += qty
            if qty >= self.large_trade_threshold_btc:
                self._large_buy_count += 1
        else:
            self._sell_volume += qty
            if qty >= self.large_trade_threshold_btc:
                self._large_sell_count += 1

        self._rolling.append((ts, signed_qty))
        self._prune_rolling(ts)

    def snapshot(self) -> dict:
        now_ts = time.time()
        self._prune_rolling(now_ts)
        net_flow = sum(v for _, v in self._rolling)

        state = OrderFlowState(
            cvd=round(self._cvd, 6),
            large_buy_count=self._large_buy_count,
            large_sell_count=self._large_sell_count,
            net_flow=round(net_flow, 6),
            buy_volume=round(self._buy_volume, 6),
            sell_volume=round(self._sell_volume, 6),
            trade_count=self._trade_count,
            large_trade_threshold_btc=round(self.large_trade_threshold_btc, 6),
            window_seconds=self.window_seconds,
            timestamp=_utc_now_iso(),
        )
        return state.to_dict()


def analyze_trade_batch(
    trades: Iterable[dict],
    large_trade_threshold_btc: float = 10.0,
    window_seconds: int = 300,
) -> dict:
    analyzer = OrderFlowAnalyzer(
        large_trade_threshold_btc=large_trade_threshold_btc,
        window_seconds=window_seconds,
    )
    for row in trades:
        if isinstance(row, dict):
            analyzer.process_trade(row)
    return analyzer.snapshot()


def fetch_recent_binance_trades(symbol: str = "BTCUSDT", limit: int = 500) -> list[dict]:
    sym = str(symbol or "BTCUSDT").upper()
    lim = max(min(int(limit), 1000), 10)
    cache_key = f"orderflow:recent:{sym}:{lim}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    resp = retry_call(
        requests.get,
        args=(BINANCE_RECENT_TRADES_URL,),
        kwargs={"params": {"symbol": sym, "limit": lim}, "timeout": 5},
        max_attempts=3,
        base_delay=0.5,
        default=None,
    )
    if resp is None or not getattr(resp, "ok", False):
        log.warn("recent trades fetch failed", symbol=sym)
        return []

    try:
        rows = resp.json() or []
        out = [r for r in rows if isinstance(r, dict)]
        set_cached(cache_key, out, ttl=2)
        return out
    except Exception as exc:
        log.warn("recent trades parse failed", symbol=sym, error=exc)
        return []


async def stream_binance_orderflow(
    symbol: str = "BTCUSDT",
    duration_seconds: int = 30,
    large_trade_threshold_btc: float = 10.0,
    window_seconds: int = 300,
) -> dict:
    sym = str(symbol or "BTCUSDT").lower()
    duration = max(int(duration_seconds), 1)
    analyzer = OrderFlowAnalyzer(
        large_trade_threshold_btc=large_trade_threshold_btc,
        window_seconds=window_seconds,
    )

    try:
        import websockets

        url = BINANCE_TRADE_WS.format(symbol=sym)
        deadline = time.time() + duration
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            while time.time() < deadline:
                timeout = max(0.1, deadline - time.time())
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    analyzer.process_trade(payload)
        return analyzer.snapshot()
    except Exception as exc:
        log.warn("websocket stream failed; fallback to recent trades", symbol=sym.upper(), error=exc)
        recent = fetch_recent_binance_trades(sym.upper(), limit=500)
        return analyze_trade_batch(
            recent,
            large_trade_threshold_btc=large_trade_threshold_btc,
            window_seconds=window_seconds,
        )


def _load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _cli() -> int:
    parser = argparse.ArgumentParser(description="BTC orderflow analyzer")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--window", type=int, default=300)
    parser.add_argument("--large-threshold", type=float, default=10.0)
    parser.add_argument("--recent-only", action="store_true", help="skip websocket, use recent trades API")
    parser.add_argument("--sample-file", default="", help="json file containing trade list")
    args = parser.parse_args()

    if args.sample_file:
        rows = _load_json_file(Path(args.sample_file))
        out = analyze_trade_batch(
            rows if isinstance(rows, list) else [],
            large_trade_threshold_btc=args.large_threshold,
            window_seconds=args.window,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.recent_only:
        rows = fetch_recent_binance_trades(args.symbol, limit=500)
        out = analyze_trade_batch(
            rows,
            large_trade_threshold_btc=args.large_threshold,
            window_seconds=args.window,
        )
    else:
        out = asyncio.run(
            stream_binance_orderflow(
                symbol=args.symbol,
                duration_seconds=args.seconds,
                large_trade_threshold_btc=args.large_threshold,
                window_seconds=args.window,
            )
        )

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
