"""Realtime-like news stream helpers for Phase 9.

This module currently uses polling with retry and cache to provide a stable,
callback-based stream interface.
"""
from __future__ import annotations

import os
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import requests

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("news_stream")

COINDESK_RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"
CRYPTOPANIC_URL = "https://cryptopanic.com/api/developer/v2/posts/"


def _request_get(url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None, timeout: int = 8):
    return retry_call(
        requests.get,
        args=(url,),
        kwargs={"params": params, "headers": headers, "timeout": timeout},
        max_attempts=3,
        base_delay=1.0,
        default=None,
    )


def _extract_sentiment(votes) -> float:
    if not isinstance(votes, dict):
        return 0.0
    pos = float(votes.get("positive", 0) or 0)
    neg = float(votes.get("negative", 0) or 0)
    den = pos + neg
    if den <= 0:
        return 0.0
    return round((pos - neg) / den, 3)


def _parse_iso_timestamp(raw: str) -> str:
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    value = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _fetch_cryptopanic_news(currencies: str = "BTC", limit: int = 20) -> List[dict]:
    api_key = os.environ.get("CRYPTOPANIC_API_KEY", "")
    if not api_key:
        return []

    params = {
        "auth_token": api_key,
        "currencies": currencies,
        "public": "true",
        "kind": "news",
        "limit": limit,
    }
    res = _request_get(CRYPTOPANIC_URL, params=params)
    if res is None:
        log.warn("cryptopanic request failed after retries")
        return []
    if not res.ok:
        log.warn("cryptopanic response not ok", status=res.status_code)
        return []

    try:
        rows = (res.json() or {}).get("results", [])
    except Exception as exc:
        log.error("cryptopanic json parse failed", error=exc)
        return []

    records: List[dict] = []
    for row in rows:
        source_obj = row.get("source") or {}
        symbols = [c.get("code") for c in row.get("currencies", []) if c.get("code")]
        ts = row.get("published_at") or row.get("created_at") or ""
        headline = row.get("title", "")
        if not headline:
            continue
        records.append(
            {
                "id": str(row.get("id") or row.get("slug") or f"{ts}:{headline}"),
                "headline": headline,
                "source": source_obj.get("title") or "CryptoPanic",
                "timestamp": _parse_iso_timestamp(ts),
                "symbols": symbols,
                "sentiment_raw": _extract_sentiment(row.get("votes")),
                "url": row.get("url", ""),
            }
        )
    return records


def _fetch_coindesk_rss(limit: int = 10) -> List[dict]:
    res = _request_get(COINDESK_RSS_URL, headers={"User-Agent": "Mozilla/5.0"})
    if res is None or not res.ok:
        return []

    try:
        root = ET.fromstring(res.content)
    except Exception as exc:
        log.error("rss parse failed", error=exc)
        return []

    items = root.findall(".//item")[:limit]
    records: List[dict] = []
    for item in items:
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub = item.findtext("pubDate", "")
        if not title:
            continue
        records.append(
            {
                "id": link or f"rss:{title}",
                "headline": title,
                "source": "CoinDesk",
                "timestamp": pub,
                "symbols": ["BTC"],
                "sentiment_raw": 0.0,
                "url": link,
            }
        )
    return records


def collect_news_once(currencies: str = "BTC", limit: int = 20) -> List[dict]:
    """Collect normalized news records.

    Output schema:
    {
      headline, source, timestamp, symbols[], sentiment_raw, url, id
    }
    """
    cache_key = f"news_stream:{currencies}:{limit}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    rows = _fetch_cryptopanic_news(currencies=currencies, limit=limit)
    if not rows:
        rows = _fetch_coindesk_rss(limit=min(limit, 10))

    set_cached(cache_key, rows, ttl=20)
    return rows


class NewsStream:
    """Polling-based callback stream for news events."""

    def __init__(self, currencies: str = "BTC", poll_interval: float = 20.0, limit: int = 20):
        self.currencies = currencies
        self.poll_interval = max(1.0, poll_interval)
        self.limit = limit
        self._callbacks: List[Callable[[dict], None]] = []
        self._seen_ids: set[str] = set()
        self._stop = threading.Event()

    def on_news(self, callback: Callable[[dict], None]) -> None:
        self._callbacks.append(callback)

    def stop(self) -> None:
        self._stop.set()

    def pump_once(self) -> List[dict]:
        rows = collect_news_once(currencies=self.currencies, limit=self.limit)
        if not rows:
            return []

        fresh: List[dict] = []
        for item in reversed(rows):  # deliver oldest->newest
            item_id = str(item.get("id", ""))
            if not item_id or item_id in self._seen_ids:
                continue
            self._seen_ids.add(item_id)
            fresh.append(item)
            for cb in self._callbacks:
                try:
                    cb(item)
                except Exception as exc:
                    log.error("news callback failed", error=exc)
        return fresh

    def run_forever(self) -> None:
        log.info("news stream started", currencies=self.currencies, poll_interval=self.poll_interval)
        while not self._stop.is_set():
            try:
                self.pump_once()
            except Exception as exc:
                log.error("news stream loop failed", error=exc)
            self._stop.wait(self.poll_interval)


if __name__ == "__main__":
    stream = NewsStream(currencies="BTC", poll_interval=15)

    def _printer(item: Dict):
        log.info("news", headline=item.get("headline"), source=item.get("source"))

    stream.on_news(_printer)
    try:
        stream.run_forever()
    except KeyboardInterrupt:
        stream.stop()
        log.info("news stream stopped")
