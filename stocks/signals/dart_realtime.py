"""DART realtime disclosure filter (Phase 15)."""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call

load_env()
log = get_logger("dart_realtime")

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"


KEYWORDS = {
    "BUYBACK": ["자기주식", "자사주", "취득결정", "소각"],
    "RIGHTS_ISSUE": ["유상증자", "신주발행", "주주배정"],
    "EARNINGS": ["잠정실적", "영업실적", "실적발표", "매출액"],
    "MAJOR_CONTRACT": ["공급계약", "수주", "단일판매", "대규모계약"],
}


@dataclass
class DARTSignal:
    corp_code: str
    corp_name: str
    stock_code: str
    report_name: str
    category: str
    signal: str
    score: float
    reason: str
    receipt_no: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _contains_any(text: str, words: list[str]) -> bool:
    t = str(text or "").lower()
    return any(str(w).lower() in t for w in words)


def classify_disclosure(report_name: str, detail: str = "") -> dict:
    text = f"{report_name} {detail}".strip()

    if _contains_any(text, KEYWORDS["RIGHTS_ISSUE"]):
        return {
            "category": "RIGHTS_ISSUE",
            "signal": "SELL_STRONG",
            "score": -1.0,
            "reason": "rights issue dilution risk",
        }
    if _contains_any(text, KEYWORDS["BUYBACK"]):
        return {
            "category": "BUYBACK",
            "signal": "BUY_STRONG",
            "score": 1.0,
            "reason": "buyback disclosure",
        }
    if _contains_any(text, KEYWORDS["MAJOR_CONTRACT"]):
        return {
            "category": "MAJOR_CONTRACT",
            "signal": "BUY",
            "score": 0.6,
            "reason": "major contract momentum",
        }
    if _contains_any(text, KEYWORDS["EARNINGS"]):
        return {
            "category": "EARNINGS",
            "signal": "WATCH",
            "score": 0.2,
            "reason": "earnings-related disclosure",
        }

    return {
        "category": "OTHER",
        "signal": "NEUTRAL",
        "score": 0.0,
        "reason": "no actionable keyword",
    }


class DARTRealtimeFilter:
    def __init__(self, cache_ttl_seconds: int = 60):
        self.cache_ttl_seconds = max(int(cache_ttl_seconds), 30)

    def _seen_key(self) -> str:
        return "dart_realtime:seen_receipts"

    def _load_seen(self) -> set[str]:
        rows = get_cached(self._seen_key())
        if rows is None:
            rows = []
        return set(str(x) for x in rows if x)

    def _save_seen(self, seen: set[str]) -> None:
        set_cached(self._seen_key(), sorted(seen), ttl=24 * 3600)

    def fetch_recent(self, page_count: int = 1) -> list[dict]:
        api_key = os.environ.get("DART_API_KEY", "")
        if not api_key:
            return []

        cache_key = f"dart_realtime:list:{page_count}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached

        today = datetime.now().strftime("%Y%m%d")
        rows: list[dict] = []
        for page_no in range(1, max(int(page_count), 1) + 1):
            resp = retry_call(
                requests.get,
                args=(DART_LIST_URL,),
                kwargs={
                    "params": {
                        "crtfc_key": api_key,
                        "bgn_de": today,
                        "end_de": today,
                        "page_count": 100,
                        "page_no": page_no,
                    },
                    "timeout": 8,
                },
                max_attempts=2,
                base_delay=0.7,
                default=None,
            )
            if resp is None or not getattr(resp, "ok", False):
                continue
            try:
                payload = resp.json() or {}
                rows.extend(payload.get("list") or [])
            except Exception as exc:
                log.warn("dart parse failed", page=page_no, error=exc)

        clean = [r for r in rows if isinstance(r, dict)]
        set_cached(cache_key, clean, ttl=self.cache_ttl_seconds)
        return clean

    def classify_rows(self, rows: list[dict], dedupe: bool = True) -> list[dict]:
        seen = self._load_seen() if dedupe else set()
        out: list[dict] = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            receipt = str(row.get("rcept_no") or row.get("receipt_no") or "")
            if dedupe and receipt and receipt in seen:
                continue

            report_name = str(row.get("report_nm") or "")
            detail = str(row.get("rm") or row.get("flr_nm") or "")
            cls = classify_disclosure(report_name, detail)

            sig = DARTSignal(
                corp_code=str(row.get("corp_code") or ""),
                corp_name=str(row.get("corp_name") or ""),
                stock_code=str(row.get("stock_code") or ""),
                report_name=report_name,
                category=cls["category"],
                signal=cls["signal"],
                score=_safe_float(cls.get("score"), 0.0),
                reason=cls["reason"],
                receipt_no=receipt,
                timestamp=_utc_now_iso(),
            )
            out.append(sig.to_dict())
            if dedupe and receipt:
                seen.add(receipt)

        if dedupe:
            self._save_seen(seen)
        return out

    def scan(self, page_count: int = 1, dedupe: bool = True) -> dict:
        rows = self.fetch_recent(page_count=page_count)
        signals = self.classify_rows(rows, dedupe=dedupe)

        buy_signals = [s for s in signals if s.get("signal") in {"BUY", "BUY_STRONG"}]
        sell_signals = [s for s in signals if s.get("signal") == "SELL_STRONG"]

        return {
            "count": len(signals),
            "buy_count": len(buy_signals),
            "sell_count": len(sell_signals),
            "signals": signals,
            "timestamp": _utc_now_iso(),
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="DART realtime disclosure filter")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--no-dedupe", action="store_true")
    parser.add_argument("--sample-file", default="", help="json list file")
    args = parser.parse_args()

    filt = DARTRealtimeFilter()
    if args.sample_file:
        with open(args.sample_file, "r", encoding="utf-8") as f:
            rows = json.load(f)
        signals = filt.classify_rows(rows if isinstance(rows, list) else [], dedupe=not args.no_dedupe)
        out = {
            "count": len(signals),
            "buy_count": len([s for s in signals if s.get("signal") in {"BUY", "BUY_STRONG"}]),
            "sell_count": len([s for s in signals if s.get("signal") == "SELL_STRONG"]),
            "signals": signals,
            "timestamp": _utc_now_iso(),
        }
    else:
        out = filt.scan(page_count=args.pages, dedupe=not args.no_dedupe)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
