"""Alternative data collectors for Phase 9.

Normalized output schema:
{
  symbol,
  search_trend_7d,
  social_mentions_24h,
  sentiment_score,
}
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict

import requests

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("alt_data")

CRYPTOPANIC_URL = "https://cryptopanic.com/api/developer/v2/posts/"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_get(url: str, *, params: dict, timeout: int = 8):
    return retry_call(
        requests.get,
        args=(url,),
        kwargs={"params": params, "timeout": timeout},
        max_attempts=3,
        base_delay=1.0,
        default=None,
    )


def _trend_keyword(symbol: str) -> str:
    sym = symbol.upper().strip()
    if sym in {"BTC", "KRW-BTC", "BTCUSDT"}:
        return "Bitcoin"
    return sym


def get_google_trend(symbol: str, window_days: int = 7) -> Dict:
    """Get Google Trends signal for symbol keyword.

    Returns:
      {keyword, search_trend_7d, trend_slope, sample_count, timestamp, source}
    """
    keyword = _trend_keyword(symbol)
    cache_key = f"alt_data:trend:{keyword}:{window_days}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    out = {
        "keyword": keyword,
        "search_trend_7d": 0.0,
        "trend_slope": 0.0,
        "sample_count": 0,
        "timestamp": _utc_now_iso(),
        "source": "pytrends",
    }

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=540)
        timeframe = f"now {max(window_days, 1)}-d"
        pytrends.build_payload([keyword], timeframe=timeframe)
        df = pytrends.interest_over_time()
        if df is None or df.empty or keyword not in df.columns:
            set_cached(cache_key, out, ttl=900)
            return out

        series = df[keyword].astype(float)
        out.update(
            {
                "search_trend_7d": round(float(series.iloc[-1]), 2),
                "trend_slope": round(float(series.iloc[-1] - series.iloc[0]), 2),
                "sample_count": int(len(series)),
            }
        )
    except ImportError:
        out["source"] = "pytrends_unavailable"
        log.warn("pytrends is not installed; trend fallback used")
    except Exception as exc:
        out["source"] = "pytrends_error"
        log.warn("pytrends fetch failed", error=exc)

    set_cached(cache_key, out, ttl=900)
    return out


def get_social_mentions(symbol: str, hours: int = 24) -> Dict:
    """Estimate social/news mentions using CryptoPanic post counts and vote balance."""
    sym = symbol.upper().replace("KRW-", "")
    cache_key = f"alt_data:social:{sym}:{hours}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    out = {
        "symbol": sym,
        "social_mentions_24h": 0,
        "sentiment_score": 0.0,
        "positive_votes": 0,
        "negative_votes": 0,
        "timestamp": _utc_now_iso(),
        "source": "cryptopanic",
    }

    api_key = os.environ.get("CRYPTOPANIC_API_KEY", "")
    if not api_key:
        out["source"] = "cryptopanic_unavailable"
        set_cached(cache_key, out, ttl=300)
        return out

    params = {
        "auth_token": api_key,
        "currencies": sym,
        "public": "true",
        "kind": "news",
        "limit": 50,
    }
    res = _request_get(CRYPTOPANIC_URL, params=params)
    if res is None or not res.ok:
        out["source"] = "cryptopanic_error"
        set_cached(cache_key, out, ttl=120)
        return out

    try:
        rows = (res.json() or {}).get("results", [])
        pos = 0
        neg = 0
        for row in rows:
            votes = row.get("votes") or {}
            pos += int(votes.get("positive", 0) or 0)
            neg += int(votes.get("negative", 0) or 0)

        den = pos + neg
        score = (pos - neg) / den if den > 0 else 0.0
        out.update(
            {
                "social_mentions_24h": int(len(rows)),
                "sentiment_score": round(float(score), 3),
                "positive_votes": int(pos),
                "negative_votes": int(neg),
            }
        )
    except Exception as exc:
        out["source"] = "cryptopanic_parse_error"
        log.warn("cryptopanic parse failed", error=exc)

    set_cached(cache_key, out, ttl=300)
    return out


def get_alternative_data(symbol: str) -> Dict:
    """Return merged alternative-data snapshot for a symbol."""
    trend = get_google_trend(symbol)
    social = get_social_mentions(symbol)
    return {
        "symbol": symbol.upper(),
        "search_trend_7d": trend.get("search_trend_7d", 0.0),
        "social_mentions_24h": social.get("social_mentions_24h", 0),
        "sentiment_score": social.get("sentiment_score", 0.0),
        "trend": trend,
        "social": social,
        "timestamp": _utc_now_iso(),
    }


if __name__ == "__main__":
    snapshot = get_alternative_data("BTC")
    log.info(
        "alt_data",
        symbol=snapshot.get("symbol"),
        trend=snapshot.get("search_trend_7d"),
        mentions=snapshot.get("social_mentions_24h"),
        sentiment=snapshot.get("sentiment_score"),
    )
