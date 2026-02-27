"""Exposure management for sectors/factors/countries (Phase 11)."""
from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional

from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("risk_exposure")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _position_value(position: dict) -> float:
    value = _safe_float(
        position.get("market_value")
        or position.get("value")
        or position.get("notional")
        or position.get("exposure"),
        0.0,
    )
    if value > 0:
        return value
    qty = _safe_float(position.get("quantity") or position.get("qty"), 0.0)
    px = _safe_float(position.get("current_price") or position.get("price") or position.get("entry_price"), 0.0)
    return max(0.0, qty * px)


def _infer_country(position: dict) -> str:
    country = str(position.get("country") or "").strip().upper()
    if country:
        return country
    market = str(position.get("market") or "").strip().lower()
    if market in {"kr", "kospi", "kosdaq", "kq", "ks"}:
        return "KR"
    if market in {"us", "nyse", "nasdaq"}:
        return "US"
    if market in {"btc", "crypto", "coin", "upbit", "binance"}:
        return "BTC"
    symbol = _normalize_symbol(position.get("symbol") or position.get("ticker") or position.get("code"))
    if symbol in {"BTC", "BTC-USD", "KRW-BTC", "BTCUSDT"}:
        return "BTC"
    if symbol.endswith(".KS") or symbol.endswith(".KQ") or symbol.isdigit():
        return "KR"
    return "UNKNOWN"


def _weighted_group(values: Dict[str, float], total: float) -> Dict[str, float]:
    if total <= 0:
        return {}
    return {k: v / total for k, v in values.items() if v > 0}


def _default_factor_groups() -> Dict[str, List[str]]:
    return {
        "momentum": ["momentum_12m", "momentum_1m", "rsi_14d", "macd_signal"],
        "value": ["pe_ratio", "pb_ratio", "ev_ebitda"],
        "quality": ["roe", "roa", "debt_ratio", "earnings_surprise", "revenue_growth", "accruals"],
        "sentiment": ["fg_index", "social_sentiment", "search_trend"],
        "technical": ["volume_ratio_20d", "atr_pct", "bb_position"],
        "alternative": ["orderbook_imbalance"],
    }


def _sector_from_position(position: dict, yfinance_fallback: bool = False) -> str:
    sector = str(position.get("sector") or position.get("industry") or "").strip()
    if sector:
        return sector

    if not yfinance_fallback:
        return "UNKNOWN"

    symbol = _normalize_symbol(position.get("symbol") or position.get("ticker") or position.get("code"))
    if not symbol or symbol.isdigit():
        return "UNKNOWN"
    try:
        import yfinance as yf

        info = retry_call(
            yf.Ticker(symbol).get_info,
            max_attempts=1,
            base_delay=0.2,
            default=None,
        )
        if not info:
            info = yf.Ticker(symbol).info or {}
        return str(info.get("sector") or info.get("industry") or "UNKNOWN")
    except Exception:
        return "UNKNOWN"


class ExposureManager:
    def __init__(self, sector_limit: float = 0.30):
        self.sector_limit = max(0.0, min(1.0, sector_limit))

    def sector_exposure(
        self,
        positions: List[dict],
        yfinance_fallback: bool = False,
    ) -> dict:
        sector_values: Dict[str, float] = {}
        total = 0.0
        for p in positions:
            v = _position_value(p)
            if v <= 0:
                continue
            sector = _sector_from_position(p, yfinance_fallback=yfinance_fallback)
            sector_values[sector] = sector_values.get(sector, 0.0) + v
            total += v

        exposure = _weighted_group(sector_values, total)
        breaches = [
            {"sector": s, "weight": round(w, 6)}
            for s, w in exposure.items()
            if w > self.sector_limit
        ]
        breaches.sort(key=lambda x: x["weight"], reverse=True)

        return {
            "sector_limit": self.sector_limit,
            "sector_exposure": {k: round(v, 6) for k, v in sorted(exposure.items(), key=lambda x: x[1], reverse=True)},
            "breaches": breaches,
        }

    def country_exposure(self, positions: List[dict]) -> dict:
        country_values: Dict[str, float] = {}
        total = 0.0
        for p in positions:
            v = _position_value(p)
            if v <= 0:
                continue
            c = _infer_country(p)
            country_values[c] = country_values.get(c, 0.0) + v
            total += v

        exposure = _weighted_group(country_values, total)
        return {
            "country_exposure": {k: round(v, 6) for k, v in sorted(exposure.items(), key=lambda x: x[1], reverse=True)},
            "total_value": round(total, 6),
        }

    def factor_exposure(
        self,
        positions: List[dict],
        factor_snapshot: Mapping[str, Mapping[str, float]],
        factor_groups: Optional[Mapping[str, Iterable[str]]] = None,
    ) -> dict:
        groups = {k: list(v) for k, v in (factor_groups or _default_factor_groups()).items()}

        total = 0.0
        weighted_by_group = {g: 0.0 for g in groups.keys()}

        for p in positions:
            symbol = _normalize_symbol(p.get("symbol") or p.get("ticker") or p.get("code"))
            v = _position_value(p)
            if not symbol or v <= 0:
                continue
            total += v

            factors = factor_snapshot.get(symbol) or {}
            for g, names in groups.items():
                vals = [_safe_float(factors.get(n), 0.0) for n in names]
                if not vals:
                    continue
                grp_score = sum(vals) / len(vals)
                weighted_by_group[g] += v * grp_score

        if total <= 0:
            exposure = {g: 0.0 for g in groups.keys()}
        else:
            exposure = {g: weighted_by_group[g] / total for g in groups.keys()}

        return {
            "factor_exposure": {k: round(v, 6) for k, v in sorted(exposure.items(), key=lambda x: abs(x[1]), reverse=True)},
            "groups": groups,
        }

    def summarize(
        self,
        positions: List[dict],
        factor_snapshot: Optional[Mapping[str, Mapping[str, float]]] = None,
        yfinance_fallback: bool = False,
    ) -> dict:
        sec = self.sector_exposure(positions, yfinance_fallback=yfinance_fallback)
        ctry = self.country_exposure(positions)
        fac = self.factor_exposure(positions, factor_snapshot or {})

        return {
            "sector": sec,
            "country": ctry,
            "factor": fac,
            "is_sector_limit_ok": len(sec.get("breaches", [])) == 0,
        }


if __name__ == "__main__":
    sample_positions = [
        {"symbol": "AAPL", "market": "us", "market_value": 30000, "sector": "Technology"},
        {"symbol": "MSFT", "market": "us", "market_value": 25000, "sector": "Technology"},
        {"symbol": "005930", "market": "kr", "market_value": 20000, "sector": "Semiconductor"},
        {"symbol": "BTC", "market": "btc", "market_value": 10000, "sector": "Crypto"},
    ]
    sample_factors = {
        "AAPL": {"momentum_1m": 3.2, "pe_ratio": -26.4, "roe": 145.0},
        "MSFT": {"momentum_1m": 2.4, "pe_ratio": -31.1, "roe": 38.2},
        "005930": {"momentum_1m": 1.1, "pe_ratio": -12.2, "roe": 9.8},
        "BTC": {"momentum_1m": 4.6, "fg_index": 72, "social_sentiment": 0.24},
    }
    mgr = ExposureManager(sector_limit=0.30)
    out = mgr.summarize(sample_positions, factor_snapshot=sample_factors)
    log.info("exposure", breaches=len(out["sector"]["breaches"]))
