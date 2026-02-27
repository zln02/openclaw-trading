"""Sector rotation model (Phase 15)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("sector_rotation")

DEFAULT_SECTOR_PROXY = {
    "COMMUNICATION": "XLC",
    "CONSUMER_DISCRETIONARY": "XLY",
    "CONSUMER_STAPLES": "XLP",
    "ENERGY": "XLE",
    "FINANCIALS": "XLF",
    "HEALTH_CARE": "XLV",
    "INDUSTRIALS": "XLI",
    "MATERIALS": "XLB",
    "REAL_ESTATE": "XLRE",
    "TECHNOLOGY": "XLK",
    "UTILITIES": "XLU",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value or "").strip()
    if len(s) >= 10:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    return date.today()


def rank_sector_strength(sector_returns: dict[str, float], top_n: int = 3, bottom_n: int = 3) -> dict:
    items = [
        {"sector": str(k), "return_pct": round(_safe_float(v, 0.0), 6)}
        for k, v in (sector_returns or {}).items()
    ]
    items.sort(key=lambda x: x["return_pct"], reverse=True)

    return {
        "ranked": items,
        "top": items[: max(int(top_n), 0)],
        "bottom": items[-max(int(bottom_n), 0) :] if bottom_n > 0 else [],
    }


@dataclass
class SectorRotationDecision:
    month: str
    top_sectors: list[str]
    avoid_sectors: list[str]
    ranked: list[dict]
    rebalance_due: bool
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class SectorRotationModel:
    def __init__(self, price_fetcher: Optional[Callable[[dict[str, str], int], dict[str, list[float]]]] = None):
        self.price_fetcher = price_fetcher

    def _fetch_yfinance_prices(self, proxy_map: dict[str, str], lookback_days: int) -> dict[str, list[float]]:
        try:
            import yfinance as yf
        except Exception:
            return {}

        out: dict[str, list[float]] = {}
        for sector, ticker in proxy_map.items():
            try:
                hist = yf.Ticker(ticker).history(period=f"{max(int(lookback_days), 30)}d")
                if hist is None or hist.empty:
                    continue
                closes = [float(x) for x in hist["Close"].tolist() if _safe_float(x, 0.0) > 0]
                if len(closes) >= 2:
                    out[sector] = closes
            except Exception as exc:
                log.warn("sector history fetch failed", sector=sector, ticker=ticker, error=exc)
        return out

    def compute_sector_returns(self, prices_by_sector: dict[str, list[float]]) -> dict[str, float]:
        out: dict[str, float] = {}
        for sector, values in (prices_by_sector or {}).items():
            vals = [_safe_float(v, 0.0) for v in values if _safe_float(v, 0.0) > 0]
            if len(vals) < 2:
                continue
            ret = (vals[-1] / vals[0] - 1.0) * 100.0
            out[str(sector)] = round(ret, 6)
        return out

    def is_rebalance_due(self, last_rebalance_date: Optional[str], as_of: Optional[str] = None) -> bool:
        today = _to_date(as_of)
        if not last_rebalance_date:
            return True

        try:
            last = _to_date(last_rebalance_date)
        except Exception:
            return True

        return (today.year, today.month) != (last.year, last.month)

    def build_monthly_rotation(
        self,
        prices_by_sector: Optional[dict[str, list[float]]] = None,
        last_rebalance_date: Optional[str] = None,
        as_of: Optional[str] = None,
        lookback_days: int = 63,
        top_n: int = 3,
        bottom_n: int = 3,
    ) -> dict:
        data = prices_by_sector
        if data is None:
            if self.price_fetcher is not None:
                data = self.price_fetcher(DEFAULT_SECTOR_PROXY, lookback_days)
            else:
                data = self._fetch_yfinance_prices(DEFAULT_SECTOR_PROXY, lookback_days)

        returns = self.compute_sector_returns(data or {})
        ranked = rank_sector_strength(returns, top_n=top_n, bottom_n=bottom_n)

        rebalance_due = self.is_rebalance_due(last_rebalance_date, as_of=as_of)
        top = [x["sector"] for x in ranked["top"]]
        bottom = [x["sector"] for x in ranked["bottom"]]

        reason = "monthly rebalance due" if rebalance_due else "within same month"
        out = SectorRotationDecision(
            month=_to_date(as_of).strftime("%Y-%m") if as_of else date.today().strftime("%Y-%m"),
            top_sectors=top,
            avoid_sectors=bottom,
            ranked=ranked["ranked"],
            rebalance_due=rebalance_due,
            reason=reason,
            timestamp=_utc_now_iso(),
        )
        return out.to_dict()


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Sector rotation model")
    parser.add_argument("--sample-file", default="", help="json sector->price_list mapping")
    parser.add_argument("--lookback", type=int, default=63)
    parser.add_argument("--last-rebalance", default="")
    parser.add_argument("--as-of", default="")
    args = parser.parse_args()

    model = SectorRotationModel()
    if args.sample_file:
        with open(args.sample_file, "r", encoding="utf-8") as f:
            prices = json.load(f)
        out = model.build_monthly_rotation(
            prices_by_sector=prices if isinstance(prices, dict) else {},
            last_rebalance_date=args.last_rebalance or None,
            as_of=args.as_of or None,
            lookback_days=args.lookback,
        )
    else:
        out = model.build_monthly_rotation(
            prices_by_sector=None,
            last_rebalance_date=args.last_rebalance or None,
            as_of=args.as_of or None,
            lookback_days=args.lookback,
        )

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
