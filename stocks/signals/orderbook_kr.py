"""KR orderbook depth analyzer (Phase 15).

- 10-level bid/ask depth imbalance
- Wall detection (abnormal depth concentration)
- Short-horizon directional bias
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any, Callable, Optional

from common.data.orderbook import fetch_kr_orderbook_snapshot
from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("orderbook_kr")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_levels(levels: list[dict], limit: int = 10) -> list[dict]:
    out: list[dict] = []
    for row in levels[:limit]:
        if not isinstance(row, dict):
            continue
        price = _safe_float(row.get("price"), 0.0)
        qty = _safe_float(row.get("qty"), 0.0)
        if price <= 0 or qty < 0:
            continue
        out.append({"price": price, "qty": qty})
    return out


def _detect_walls(levels: list[dict], wall_multiplier: float) -> list[dict]:
    if not levels:
        return []
    qtys = [max(_safe_float(x.get("qty"), 0.0), 0.0) for x in levels]
    base = median(qtys) if qtys else 0.0
    if base <= 0:
        return []

    walls = []
    for lv in levels:
        qty = max(_safe_float(lv.get("qty"), 0.0), 0.0)
        if qty >= base * wall_multiplier:
            walls.append({
                "price": _safe_float(lv.get("price"), 0.0),
                "qty": round(qty, 4),
                "ratio_vs_median": round(qty / base, 4),
            })
    return walls


@dataclass
class KROrderbookSignal:
    symbol: str
    bid_ask_ratio: float
    imbalance: float
    buy_depth: float
    sell_depth: float
    wall_bid_count: int
    wall_ask_count: int
    direction: str
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_orderbook_snapshot(snapshot: dict, wall_multiplier: float = 3.0) -> dict:
    bids = _normalize_levels(snapshot.get("bids") or [], limit=10)
    asks = _normalize_levels(snapshot.get("asks") or [], limit=10)

    buy_depth = sum(_safe_float(x.get("qty"), 0.0) for x in bids)
    sell_depth = sum(_safe_float(x.get("qty"), 0.0) for x in asks)

    ratio = buy_depth / sell_depth if sell_depth > 0 else (999.0 if buy_depth > 0 else 1.0)
    den = buy_depth + sell_depth
    imbalance = ((buy_depth - sell_depth) / den) if den > 0 else 0.0

    bid_walls = _detect_walls(bids, max(_safe_float(wall_multiplier, 3.0), 1.2))
    ask_walls = _detect_walls(asks, max(_safe_float(wall_multiplier, 3.0), 1.2))

    if ratio >= 1.25 and imbalance >= 0.10:
        direction = "BULLISH"
        reason = "buy depth dominates"
    elif ratio <= 0.80 and imbalance <= -0.10:
        direction = "BEARISH"
        reason = "sell depth dominates"
    else:
        direction = "NEUTRAL"
        reason = "balanced depth"

    if bid_walls and not ask_walls:
        reason += " + bid wall support"
    elif ask_walls and not bid_walls:
        reason += " + ask wall resistance"

    out = KROrderbookSignal(
        symbol=str(snapshot.get("symbol") or "").upper(),
        bid_ask_ratio=round(ratio, 6),
        imbalance=round(imbalance, 6),
        buy_depth=round(buy_depth, 4),
        sell_depth=round(sell_depth, 4),
        wall_bid_count=len(bid_walls),
        wall_ask_count=len(ask_walls),
        direction=direction,
        reason=reason,
        timestamp=str(snapshot.get("timestamp") or _utc_now_iso()),
    ).to_dict()
    out["bid_walls"] = bid_walls
    out["ask_walls"] = ask_walls
    return out


class KROrderbookAnalyzer:
    def __init__(
        self,
        snapshot_fetcher: Optional[Callable[[str], dict]] = None,
        wall_multiplier: float = 3.0,
    ):
        self.snapshot_fetcher = snapshot_fetcher
        self.wall_multiplier = wall_multiplier

    def _fetch_snapshot(self, symbol: str, kiwoom_client=None) -> dict:
        if self.snapshot_fetcher is not None:
            return self.snapshot_fetcher(symbol)
        return fetch_kr_orderbook_snapshot(symbol, kiwoom_client=kiwoom_client)

    def analyze(self, symbol: str, kiwoom_client=None) -> dict:
        snap = self._fetch_snapshot(symbol, kiwoom_client=kiwoom_client)
        return analyze_orderbook_snapshot(snap, wall_multiplier=self.wall_multiplier)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="KR orderbook depth analyzer")
    parser.add_argument("--symbol", required=True, help="KR code e.g., 005930")
    parser.add_argument("--wall-multiplier", type=float, default=3.0)
    parser.add_argument("--sample-file", default="", help="load orderbook snapshot JSON")
    args = parser.parse_args()

    if args.sample_file:
        with open(args.sample_file, "r", encoding="utf-8") as f:
            snap = json.load(f)
        out = analyze_orderbook_snapshot(snap, wall_multiplier=args.wall_multiplier)
    else:
        out = KROrderbookAnalyzer(wall_multiplier=args.wall_multiplier).analyze(args.symbol)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
