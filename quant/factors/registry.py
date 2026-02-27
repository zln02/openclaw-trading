"""Phase 10 factor registry.

This module provides:
- @register_factor(name, category, universe)
- calc(date, symbol) -> float
- calc_all(date, symbol) -> dict[str, float]

Categories supported:
momentum, value, quality, sentiment, technical, alternative
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Dict, Iterable, List, Optional

import requests

from common.cache import get_cached, set_cached
from common.data import fetch_binance_orderbook, fetch_upbit_orderbook, get_alternative_data
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call
from common.supabase_client import get_supabase

load_env()
log = get_logger("factor_registry")


FactorFn = Callable[["FactorContext", str, str, str], float]


@dataclass(frozen=True)
class FactorDefinition:
    name: str
    category: str
    universe: str
    fn: FactorFn


FACTOR_REGISTRY: Dict[str, FactorDefinition] = {}


def register_factor(name: str, category: str, universe: str = "all"):
    """Register a factor function.

    Factor function signature:
        fn(ctx, symbol, as_of_iso, market) -> float
    """

    def decorator(fn: FactorFn):
        key = name.strip()
        if not key:
            raise ValueError("factor name is required")
        FACTOR_REGISTRY[key] = FactorDefinition(
            name=key,
            category=category.strip().lower() or "unknown",
            universe=universe.strip().lower() or "all",
            fn=fn,
        )
        return fn

    return decorator


def _to_iso_day(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text[:10] if len(text) >= 10 else text


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return float(math.sqrt(var))


def _calc_return(close: List[float], lookback: int) -> float:
    if len(close) <= lookback:
        return 0.0
    prev = _safe_float(close[-1 - lookback])
    cur = _safe_float(close[-1])
    if prev <= 0:
        return 0.0
    return (cur / prev) - 1.0


def _ema(series: List[float], period: int) -> List[float]:
    if not series:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [float(series[0])]
    for x in series[1:]:
        out.append(alpha * float(x) + (1.0 - alpha) * out[-1])
    return out


def _calc_rsi(close: List[float], period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(-period, 0):
        diff = float(close[i]) - float(close[i - 1])
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = _mean(gains)
    avg_loss = _mean(losses)
    if avg_loss <= 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _calc_macd_signal_delta(close: List[float]) -> float:
    if len(close) < 35:
        return 0.0
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd = [a - b for a, b in zip(ema12, ema26)]
    sig = _ema(macd, 9)
    if not macd or not sig:
        return 0.0
    return float(macd[-1] - sig[-1])


def _calc_bb_position(close: List[float], period: int = 20) -> float:
    if len(close) < period:
        return 50.0
    window = [float(x) for x in close[-period:]]
    m = _mean(window)
    s = _std(window)
    upper = m + 2.0 * s
    lower = m - 2.0 * s
    width = upper - lower
    if width <= 0:
        return 50.0
    pos = (float(close[-1]) - lower) / width * 100.0
    return float(max(0.0, min(100.0, pos)))


def _calc_volume_ratio(rows: List[dict], period: int = 20) -> float:
    if len(rows) < period + 1:
        return 1.0
    vols = [_safe_float(r.get("volume"), 0.0) for r in rows]
    recent = vols[-1]
    avg = _mean(vols[-period - 1 : -1])
    if avg <= 0:
        return 1.0
    return float(recent / avg)


def _calc_atr_pct(rows: List[dict], period: int = 14) -> float:
    if len(rows) < period + 1:
        return 0.0
    trs: List[float] = []
    for i in range(-period, 0):
        cur = rows[i]
        prev_close = _safe_float(rows[i - 1].get("close"), 0.0)
        high = _safe_float(cur.get("high"), 0.0)
        low = _safe_float(cur.get("low"), 0.0)
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(max(tr, 0.0))
    atr = _mean(trs)
    price = _safe_float(rows[-1].get("close"), 0.0)
    if price <= 0:
        return 0.0
    return float(atr / price)


class FactorContext:
    """Shared data access object for factor calculations."""

    def __init__(self, supabase_client=None):
        self.supabase = supabase_client or get_supabase()
        self._series_cache: Dict[str, List[dict]] = {}
        self._fund_cache: Dict[str, dict] = {}

    @staticmethod
    def normalize_symbol(symbol: str, market: str) -> str:
        s = str(symbol or "").strip().upper()
        mk = market.lower().strip()
        if mk == "kr":
            return s.lstrip("A")
        return s

    def _yf_symbol(self, symbol: str, market: str) -> str:
        s = self.normalize_symbol(symbol, market)
        mk = market.lower().strip()
        if mk == "kr":
            if s.endswith(".KS") or s.endswith(".KQ"):
                return s
            return f"{s}.KS"
        if mk == "btc":
            return "BTC-USD"
        return s

    def _series_key(self, symbol: str, market: str) -> str:
        return f"{market.lower()}:{self.normalize_symbol(symbol, market)}"

    def _load_series_from_supabase(self, symbol: str, market: str) -> List[dict]:
        if not self.supabase:
            return []
        mk = market.lower().strip()
        if mk not in {"kr", "btc"}:
            return []

        code = self.normalize_symbol(symbol, market)
        if mk == "btc":
            # BTC currently sourced from yfinance in this phase.
            return []

        try:
            rows = (
                self.supabase.table("daily_ohlcv")
                .select("date,open_price,high_price,low_price,close_price,volume")
                .eq("stock_code", code)
                .order("date", desc=False)
                .limit(5000)
                .execute()
                .data
                or []
            )
            out = []
            for r in rows:
                out.append(
                    {
                        "date": str(r.get("date") or "")[:10],
                        "open": _safe_float(r.get("open_price")),
                        "high": _safe_float(r.get("high_price")),
                        "low": _safe_float(r.get("low_price")),
                        "close": _safe_float(r.get("close_price")),
                        "volume": _safe_float(r.get("volume")),
                    }
                )
            return out
        except Exception as exc:
            log.warn("supabase series fetch failed", symbol=symbol, market=market, error=exc)
            return []

    def _load_series_from_yfinance(self, symbol: str, market: str) -> List[dict]:
        try:
            import yfinance as yf

            ticker = self._yf_symbol(symbol, market)
            t = yf.Ticker(ticker)
            hist = retry_call(
                t.history,
                kwargs={"period": "10y", "interval": "1d"},
                max_attempts=2,
                base_delay=1.0,
                default=None,
            )
            if hist is None or hist.empty:
                return []

            out = []
            for idx, row in hist.iterrows():
                out.append(
                    {
                        "date": str(getattr(idx, "date", lambda: idx)())[:10],
                        "open": _safe_float(row.get("Open")),
                        "high": _safe_float(row.get("High")),
                        "low": _safe_float(row.get("Low")),
                        "close": _safe_float(row.get("Close")),
                        "volume": _safe_float(row.get("Volume")),
                    }
                )
            return out
        except Exception as exc:
            log.warn("yfinance series fetch failed", symbol=symbol, market=market, error=exc)
            return []

    def get_ohlcv(self, symbol: str, as_of_iso: str, market: str = "kr", lookback: int = 400) -> List[dict]:
        key = self._series_key(symbol, market)
        if key not in self._series_cache:
            rows = self._load_series_from_supabase(symbol, market)
            if not rows:
                rows = self._load_series_from_yfinance(symbol, market)
            self._series_cache[key] = rows

        rows = self._series_cache.get(key) or []
        if not rows:
            return []
        as_of = _to_iso_day(as_of_iso)
        sliced = [r for r in rows if str(r.get("date") or "") <= as_of]
        if lookback > 0:
            sliced = sliced[-lookback:]
        return sliced

    def get_close(self, symbol: str, as_of_iso: str, market: str = "kr", lookback: int = 400) -> List[float]:
        rows = self.get_ohlcv(symbol, as_of_iso, market=market, lookback=lookback)
        return [_safe_float(r.get("close"), 0.0) for r in rows if _safe_float(r.get("close"), 0.0) > 0]

    def get_fundamentals(self, symbol: str, market: str = "kr") -> dict:
        key = f"{market.lower()}:{self.normalize_symbol(symbol, market)}"
        cached = self._fund_cache.get(key)
        if cached is not None:
            return cached

        mk = market.lower().strip()
        data: dict = {}

        if mk == "kr" and self.supabase:
            code = self.normalize_symbol(symbol, market)
            try:
                rows = (
                    self.supabase.table("financial_statements")
                    .select("*")
                    .eq("stock_code", code)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if rows:
                    r = rows[0]
                    data = {
                        "pe": _safe_float(r.get("per")),
                        "pb": _safe_float(r.get("pbr")),
                        "roe": _safe_float(r.get("roe")),
                        "roa": _safe_float(r.get("roa")),
                        "debt_ratio": _safe_float(r.get("debt_ratio")),
                        "ev_ebitda": _safe_float(r.get("ev_ebitda")),
                        "revenue_growth": _safe_float(r.get("revenue_growth")),
                        "earnings_surprise": _safe_float(r.get("earnings_surprise")),
                        "net_income": _safe_float(r.get("net_income")),
                        "operating_income": _safe_float(r.get("operating_income")),
                        "total_assets": _safe_float(r.get("total_assets")),
                    }
            except Exception as exc:
                log.warn("KR fundamentals fetch failed", symbol=symbol, error=exc)

        if not data:
            try:
                import yfinance as yf

                sym = self._yf_symbol(symbol, market)
                info = yf.Ticker(sym).info or {}
                data = {
                    "pe": _safe_float(info.get("forwardPE") or info.get("trailingPE")),
                    "pb": _safe_float(info.get("priceToBook")),
                    "roe": _safe_float(info.get("returnOnEquity")) * 100.0,
                    "roa": _safe_float(info.get("returnOnAssets")) * 100.0,
                    "debt_ratio": _safe_float(info.get("debtToEquity")),
                    "ev_ebitda": _safe_float(info.get("enterpriseToEbitda")),
                    "revenue_growth": _safe_float(info.get("revenueGrowth")) * 100.0,
                    "earnings_surprise": _safe_float(info.get("earningsQuarterlyGrowth")) * 100.0,
                    "net_income": _safe_float(info.get("netIncomeToCommon")),
                    "operating_income": _safe_float(info.get("operatingMargins"))
                    * _safe_float(info.get("totalRevenue")),
                    "total_assets": _safe_float(info.get("totalAssets")),
                }
            except Exception as exc:
                log.warn("yfinance fundamentals fetch failed", symbol=symbol, market=market, error=exc)
                data = {}

        self._fund_cache[key] = data
        return data

    def get_alt(self, symbol: str) -> dict:
        cache_key = f"factor:alt:{symbol.upper()}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        data = get_alternative_data(symbol)
        set_cached(cache_key, data, ttl=120)
        return data

    def get_fg_index(self) -> float:
        cache_key = "factor:macro:fg"
        cached = get_cached(cache_key)
        if cached is not None:
            return _safe_float(cached)

        val = 50.0
        try:
            r = retry_call(
                requests.get,
                args=("https://api.alternative.me/fng/?limit=1",),
                kwargs={"timeout": 5},
                max_attempts=2,
                base_delay=0.5,
                default=None,
            )
            if r is not None and r.ok:
                val = _safe_float((r.json() or {}).get("data", [{}])[0].get("value"), 50.0)
        except Exception:
            pass

        set_cached(cache_key, val, ttl=300)
        return val

    def get_orderbook_imbalance(self, symbol: str, market: str = "kr") -> float:
        s = str(symbol or "").upper().strip()
        mk = market.lower().strip()

        cache_key = f"factor:ob:{mk}:{s}"
        cached = get_cached(cache_key)
        if cached is not None:
            return _safe_float(cached)

        imb = 0.0
        try:
            if mk == "btc" or s in {"BTC", "BTCUSDT", "KRW-BTC"}:
                if s in {"KRW-BTC", "BTC"}:
                    snap = fetch_upbit_orderbook("KRW-BTC")
                else:
                    snap = fetch_binance_orderbook("BTCUSDT")
                imb = _safe_float(snap.get("imbalance"), 0.0)
        except Exception as exc:
            log.warn("orderbook imbalance fetch failed", symbol=symbol, market=market, error=exc)

        set_cached(cache_key, imb, ttl=2)
        return imb


def available_factors(category: Optional[str] = None, universe: Optional[str] = None) -> List[str]:
    out = []
    for name, fd in FACTOR_REGISTRY.items():
        if category and fd.category != category.lower().strip():
            continue
        if universe and fd.universe not in {"all", universe.lower().strip()}:
            continue
        out.append(name)
    return sorted(out)


def calc(
    factor_name: str,
    as_of: str | date | datetime,
    symbol: str,
    market: str = "kr",
    context: Optional[FactorContext] = None,
) -> float:
    fd = FACTOR_REGISTRY.get(factor_name)
    if fd is None:
        raise KeyError(f"factor not registered: {factor_name}")

    mk = market.lower().strip()
    if fd.universe not in {"all", mk, "krus", "kr_us"}:
        return 0.0

    ctx = context or FactorContext()
    as_of_iso = _to_iso_day(as_of)
    try:
        return _safe_float(fd.fn(ctx, symbol, as_of_iso, mk), 0.0)
    except Exception as exc:
        log.warn("factor calc failed", factor=factor_name, symbol=symbol, as_of=as_of_iso, error=exc)
        return 0.0


def calc_all(
    as_of: str | date | datetime,
    symbol: str,
    market: str = "kr",
    factor_names: Optional[Iterable[str]] = None,
    context: Optional[FactorContext] = None,
) -> Dict[str, float]:
    names = list(factor_names) if factor_names is not None else sorted(FACTOR_REGISTRY.keys())
    out: Dict[str, float] = {}
    for name in names:
        out[name] = calc(name, as_of=as_of, symbol=symbol, market=market, context=context)
    return out


# --- 20 baseline factors required by the roadmap ---


@register_factor("momentum_12m", "momentum", "all")
def factor_momentum_12m(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    close = ctx.get_close(symbol, as_of_iso, market=market, lookback=280)
    return _calc_return(close, 252) * 100.0


@register_factor("momentum_1m", "momentum", "all")
def factor_momentum_1m(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    close = ctx.get_close(symbol, as_of_iso, market=market, lookback=60)
    return _calc_return(close, 21) * 100.0


@register_factor("rsi_14d", "technical", "all")
def factor_rsi_14d(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    close = ctx.get_close(symbol, as_of_iso, market=market, lookback=80)
    return _calc_rsi(close, period=14)


@register_factor("macd_signal", "technical", "all")
def factor_macd_signal(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    close = ctx.get_close(symbol, as_of_iso, market=market, lookback=120)
    return _calc_macd_signal_delta(close)


@register_factor("pe_ratio", "value", "all")
def factor_pe_ratio(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    pe = _safe_float(ctx.get_fundamentals(symbol, market=market).get("pe"), 0.0)
    if pe <= 0:
        return 0.0
    return -pe


@register_factor("pb_ratio", "value", "all")
def factor_pb_ratio(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    pb = _safe_float(ctx.get_fundamentals(symbol, market=market).get("pb"), 0.0)
    if pb <= 0:
        return 0.0
    return -pb


@register_factor("ev_ebitda", "value", "all")
def factor_ev_ebitda(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    val = _safe_float(ctx.get_fundamentals(symbol, market=market).get("ev_ebitda"), 0.0)
    if val <= 0:
        return 0.0
    return -val


@register_factor("roe", "quality", "all")
def factor_roe(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    return _safe_float(ctx.get_fundamentals(symbol, market=market).get("roe"), 0.0)


@register_factor("roa", "quality", "all")
def factor_roa(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    return _safe_float(ctx.get_fundamentals(symbol, market=market).get("roa"), 0.0)


@register_factor("debt_ratio", "quality", "all")
def factor_debt_ratio(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    debt = _safe_float(ctx.get_fundamentals(symbol, market=market).get("debt_ratio"), 0.0)
    if debt <= 0:
        return 0.0
    return -debt


@register_factor("earnings_surprise", "quality", "all")
def factor_earnings_surprise(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    return _safe_float(ctx.get_fundamentals(symbol, market=market).get("earnings_surprise"), 0.0)


@register_factor("revenue_growth", "quality", "all")
def factor_revenue_growth(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    return _safe_float(ctx.get_fundamentals(symbol, market=market).get("revenue_growth"), 0.0)


@register_factor("accruals", "quality", "all")
def factor_accruals(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    f = ctx.get_fundamentals(symbol, market=market)
    net_income = _safe_float(f.get("net_income"), 0.0)
    operating_income = _safe_float(f.get("operating_income"), 0.0)
    assets = _safe_float(f.get("total_assets"), 0.0)
    if assets <= 0:
        return 0.0
    # lower accruals are generally better, so we negate.
    accrual = (net_income - operating_income) / assets
    return -accrual


@register_factor("volume_ratio_20d", "technical", "all")
def factor_volume_ratio_20d(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    rows = ctx.get_ohlcv(symbol, as_of_iso, market=market, lookback=60)
    return _calc_volume_ratio(rows, period=20)


@register_factor("atr_pct", "technical", "all")
def factor_atr_pct(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    rows = ctx.get_ohlcv(symbol, as_of_iso, market=market, lookback=80)
    return _calc_atr_pct(rows, period=14) * 100.0


@register_factor("bb_position", "technical", "all")
def factor_bb_position(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    close = ctx.get_close(symbol, as_of_iso, market=market, lookback=80)
    return _calc_bb_position(close, period=20)


@register_factor("fg_index", "sentiment", "all")
def factor_fg_index(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    return ctx.get_fg_index()


@register_factor("search_trend", "alternative", "all")
def factor_search_trend(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    alt = ctx.get_alt(symbol)
    return _safe_float(alt.get("search_trend_7d"), 0.0)


@register_factor("social_sentiment", "alternative", "all")
def factor_social_sentiment(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    alt = ctx.get_alt(symbol)
    return _safe_float(alt.get("sentiment_score"), 0.0)


@register_factor("orderbook_imbalance", "alternative", "all")
def factor_orderbook_imbalance(ctx: FactorContext, symbol: str, as_of_iso: str, market: str) -> float:
    mk = market
    s = str(symbol or "").upper()
    if s in {"BTC", "BTCUSDT", "KRW-BTC"}:
        mk = "btc"
    return ctx.get_orderbook_imbalance(symbol, market=mk)


if __name__ == "__main__":
    ctx = FactorContext()
    today = datetime.now().date().isoformat()
    rows = calc_all(today, symbol="005930", market="kr", context=ctx)
    log.info("factor snapshot", symbol="005930", count=len(rows))
