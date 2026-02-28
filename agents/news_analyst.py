"""Realtime news impact analyst (Phase 12).

Features:
- Consume Phase 9 normalized news items
- Classify short-term impact: POSITIVE/NEGATIVE/NEUTRAL + strength 1~5
- Maintain daily cost budget (default $2/day)
- Generate aggregated news_sentiment_score every batch
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from common.cache import get_cached, set_cached
from common.config import BRAIN_PATH
from common.data import NewsStream, collect_news_once
from common.env_loader import load_env
from common.logger import get_logger
from common.utils import safe_float as _safe_float

load_env()
log = get_logger("news_analyst")

NEWS_ANALYSIS_DIR = BRAIN_PATH / "news-analysis"
STATE_DIR = NEWS_ANALYSIS_DIR / "_state"


def _read_json_file(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("state file read failed", path=str(path), error=exc)
    return default


def _write_json_file(path: Path, payload: dict | list) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("state file write failed", path=str(path), error=exc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key(now: Optional[datetime] = None) -> str:
    return (now or _utc_now()).date().isoformat()


def _json_parse(raw: str) -> dict:
    text = (raw or "").strip().replace("```json", "").replace("```", "").strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    s = text.find("{")
    e = text.rfind("}")
    if s >= 0 and e > s:
        return json.loads(text[s : e + 1])
    raise ValueError("JSON object not found")


def _normalize_label(label: str) -> str:
    t = str(label or "").strip().upper()
    if t in {"POSITIVE", "NEGATIVE", "NEUTRAL"}:
        return t
    if t in {"BULLISH", "UP"}:
        return "POSITIVE"
    if t in {"BEARISH", "DOWN"}:
        return "NEGATIVE"
    return "NEUTRAL"


def _clip_strength(value) -> int:
    s = int(round(_safe_float(value, 3)))
    return max(1, min(5, s))


def _heuristic_analysis(item: dict, symbol: str) -> dict:
    text = f"{item.get('headline','')} {item.get('source','')}".lower()
    pos_words = [
        "surge",
        "rally",
        "beat",
        "approval",
        "bull",
        "adoption",
        "partnership",
        "record high",
        "up",
        "gain",
    ]
    neg_words = [
        "drop",
        "plunge",
        "hack",
        "ban",
        "lawsuit",
        "fraud",
        "bear",
        "downgrade",
        "down",
        "loss",
    ]
    p = sum(1 for w in pos_words if w in text)
    n = sum(1 for w in neg_words if w in text)

    if p > n:
        label = "POSITIVE"
        strength = min(5, 1 + p)
    elif n > p:
        label = "NEGATIVE"
        strength = min(5, 1 + n)
    else:
        label = "NEUTRAL"
        strength = 2

    return {
        "symbol": symbol,
        "label": label,
        "strength": int(strength),
        "reason": "heuristic",
        "confidence": 0.45,
        "model": "RULE",
    }


class NewsAnalyst:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        daily_budget_usd: float = 2.0,
        batch_minutes: int = 5,
    ):
        self.model = model
        self.daily_budget_usd = max(daily_budget_usd, 0.0)
        self.batch_minutes = max(batch_minutes, 1)

    def _budget_key(self, now: Optional[datetime] = None) -> str:
        return f"news_analyst:budget:{_today_key(now)}"

    def _seen_key(self, now: Optional[datetime] = None) -> str:
        return f"news_analyst:seen:{_today_key(now)}"

    def _budget_state_path(self, now: Optional[datetime] = None) -> Path:
        return STATE_DIR / f"budget-{_today_key(now)}.json"

    def _seen_ids_path(self, now: Optional[datetime] = None) -> Path:
        return STATE_DIR / f"seen-{_today_key(now)}.json"

    def get_budget_state(self, now: Optional[datetime] = None) -> dict:
        key = self._budget_key(now)
        state = get_cached(key)
        if state is None:
            state = _read_json_file(
                self._budget_state_path(now),
                {
                    "date": _today_key(now),
                    "spent_usd": 0.0,
                    "calls": 0,
                    "estimated_tokens": 0,
                },
            )
            set_cached(key, state, ttl=86400)
        return state

    def _save_budget_state(self, state: dict) -> None:
        now = _utc_now()
        key = self._budget_key(now)
        set_cached(key, state, ttl=86400)
        _write_json_file(self._budget_state_path(now), state)

    def _within_budget(self, estimated_increment_usd: float, now: Optional[datetime] = None) -> bool:
        st = self.get_budget_state(now)
        return _safe_float(st.get("spent_usd"), 0.0) + max(estimated_increment_usd, 0.0) <= self.daily_budget_usd

    def _estimate_cost_usd(self, prompt_text: str, completion_tokens: int = 180) -> tuple[float, int]:
        # rough estimation for gpt-4o-mini class pricing
        in_tokens = max(1, int(len(prompt_text) / 4))
        out_tokens = max(1, completion_tokens)
        # conservative estimate: $0.0002 / 1K input, $0.0008 / 1K output
        usd = (in_tokens / 1000.0) * 0.0002 + (out_tokens / 1000.0) * 0.0008
        return float(usd), int(in_tokens + out_tokens)

    def _llm_analyze(self, item: dict, symbol: str) -> Optional[dict]:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return None

        prompt = f"""
뉴스가 {symbol} 가격에 향후 1~3일 미칠 영향 분석:

headline: {item.get('headline','')}
source: {item.get('source','')}
time: {item.get('timestamp','')}

다음 JSON만 출력:
{{
  "label": "POSITIVE|NEGATIVE|NEUTRAL",
  "strength": 1,
  "reason": "20자 내 요약",
  "confidence": 0.0
}}
""".strip()

        est_cost, est_tokens = self._estimate_cost_usd(prompt, completion_tokens=180)
        if not self._within_budget(est_cost):
            return None

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=180,
            )
            raw = (res.choices[0].message.content or "").strip()
            parsed = _json_parse(raw)

            label = _normalize_label(parsed.get("label"))
            strength = _clip_strength(parsed.get("strength"))
            reason = str(parsed.get("reason") or "")[:100]
            confidence = max(0.0, min(1.0, _safe_float(parsed.get("confidence"), 0.6)))

            st = self.get_budget_state()
            st["spent_usd"] = round(_safe_float(st.get("spent_usd"), 0.0) + est_cost, 6)
            st["calls"] = int(st.get("calls", 0)) + 1
            st["estimated_tokens"] = int(st.get("estimated_tokens", 0)) + est_tokens
            self._save_budget_state(st)

            return {
                "symbol": symbol,
                "label": label,
                "strength": strength,
                "reason": reason,
                "confidence": confidence,
                "model": self.model,
                "estimated_cost_usd": round(est_cost, 6),
            }
        except Exception as exc:
            log.warning("llm news analysis failed", error=exc)
            return None

    def analyze_item(self, item: dict, symbol: str) -> dict:
        llm = self._llm_analyze(item, symbol)
        if llm is not None:
            return llm
        return _heuristic_analysis(item, symbol)

    def _batch_analyze_items(self, items: List[dict], symbol: str) -> List[Optional[dict]]:
        """Analyze multiple news items in a single LLM call.

        Returns a list aligned 1-to-1 with *items*.
        None entries mean LLM failed for that item → caller should fall back to heuristic.
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key or not items:
            return [None] * len(items)

        # Build numbered list of headlines for the batch prompt
        lines: List[str] = []
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. headline: {str(item.get('headline', ''))[:200]}")
            lines.append(f"   source: {item.get('source', '')}")
            lines.append(f"   time: {item.get('timestamp', '')}")

        prompt = (
            f"아래 {len(items)}개 뉴스가 {symbol} 가격에 향후 1~3일 미칠 영향을 각각 분석해줘.\n\n"
            + "\n".join(lines)
            + "\n\n다음 JSON 배열만 출력 (뉴스 번호 순서와 동일):\n"
            '[\n  {"idx": 1, "label": "POSITIVE|NEGATIVE|NEUTRAL", "strength": 1, "reason": "20자 내 요약", "confidence": 0.0},\n  ...\n]'
        )

        # ~100 completion tokens per item; cap at 2000
        est_cost, est_tokens = self._estimate_cost_usd(prompt, completion_tokens=min(100 * len(items), 2000))
        if not self._within_budget(est_cost):
            return [None] * len(items)

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=min(100 * len(items), 2000),
            )
            raw = (res.choices[0].message.content or "").strip()

            # Extract JSON array from response
            text = raw.replace("```json", "").replace("```", "").strip()
            s = text.find("[")
            e = text.rfind("]")
            if s < 0 or e <= s:
                raise ValueError("JSON array not found in batch response")
            parsed_list = json.loads(text[s : e + 1])

            # Update budget state once for the whole batch
            st = self.get_budget_state()
            st["spent_usd"] = round(_safe_float(st.get("spent_usd"), 0.0) + est_cost, 6)
            st["calls"] = int(st.get("calls", 0)) + 1
            st["estimated_tokens"] = int(st.get("estimated_tokens", 0)) + est_tokens
            self._save_budget_state(st)

            # Build a map keyed by 1-based idx
            result_map: dict[int, dict] = {}
            for r in parsed_list:
                if isinstance(r, dict):
                    try:
                        result_map[int(r["idx"])] = r
                    except (KeyError, ValueError, TypeError):
                        pass

            cost_per_item = round(est_cost / len(items), 6)
            results: List[Optional[dict]] = []
            for i in range(1, len(items) + 1):
                r = result_map.get(i)
                if r is None:
                    results.append(None)
                else:
                    results.append(
                        {
                            "symbol": symbol,
                            "label": _normalize_label(r.get("label")),
                            "strength": _clip_strength(r.get("strength")),
                            "reason": str(r.get("reason") or "")[:100],
                            "confidence": max(0.0, min(1.0, _safe_float(r.get("confidence"), 0.6))),
                            "model": self.model,
                            "estimated_cost_usd": cost_per_item,
                        }
                    )
            return results

        except Exception as exc:
            log.warning("batch llm news analysis failed", error=exc)
            return [None] * len(items)

    def _score_one(self, row: dict) -> float:
        label = _normalize_label(row.get("label"))
        strength = _clip_strength(row.get("strength"))
        base = strength / 5.0
        if label == "POSITIVE":
            return base
        if label == "NEGATIVE":
            return -base
        return 0.0

    def aggregate_sentiment(self, analyzed_rows: List[dict]) -> dict:
        if not analyzed_rows:
            return {
                "news_count": 0,
                "sentiment_score": 0.0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
            }

        scores = [self._score_one(r) for r in analyzed_rows]
        score = sum(scores) / len(scores)
        pos = sum(1 for r in analyzed_rows if _normalize_label(r.get("label")) == "POSITIVE")
        neg = sum(1 for r in analyzed_rows if _normalize_label(r.get("label")) == "NEGATIVE")
        neu = len(analyzed_rows) - pos - neg
        return {
            "news_count": len(analyzed_rows),
            "sentiment_score": round(score, 6),
            "positive": pos,
            "negative": neg,
            "neutral": neu,
        }

    def _load_seen_ids(self) -> set[str]:
        seen = get_cached(self._seen_key())
        if seen is None:
            seen = _read_json_file(self._seen_ids_path(), [])
            set_cached(self._seen_key(), seen, ttl=86400)
        if not seen:
            return set()
        return set(str(x) for x in seen)

    def _save_seen_ids(self, seen_ids: set[str]) -> None:
        payload = sorted(seen_ids)
        set_cached(self._seen_key(), payload, ttl=86400)
        _write_json_file(self._seen_ids_path(), payload)

    def _pick_symbol(self, item: dict, default_symbol: str) -> str:
        symbols = item.get("symbols")
        if isinstance(symbols, list):
            for s in symbols:
                sym = str(s).strip().upper()
                if sym:
                    return sym
        return str(default_symbol or "BTC").strip().upper()

    def analyze_news_items(self, items: List[dict], default_symbol: str = "BTC") -> List[dict]:
        from collections import defaultdict

        seen = self._load_seen_ids()
        now = _utc_now()

        # ── 1. Filter unseen items, assign symbol ──────────────────────────────
        # pending: list of (seq_idx, sym, item) in original order
        pending: List[tuple[int, str, dict]] = []
        for item in items:
            nid = str(item.get("id") or "")
            if not nid or nid in seen:
                continue
            seen.add(nid)
            sym = self._pick_symbol(item, default_symbol)
            pending.append((len(pending), sym, item))

        if not pending:
            self._save_seen_ids(seen)
            return []

        # ── 2. Group by symbol and batch-analyze ──────────────────────────────
        by_symbol: dict[str, List[tuple[int, dict]]] = defaultdict(list)
        for seq_idx, sym, item in pending:
            by_symbol[sym].append((seq_idx, item))

        results: dict[int, dict] = {}
        for sym, idx_items in by_symbol.items():
            batch_items = [it for _, it in idx_items]
            batch_results = self._batch_analyze_items(batch_items, sym)
            for (seq_idx, item), res in zip(idx_items, batch_results):
                if res is None:
                    res = _heuristic_analysis(item, sym)
                results[seq_idx] = res

        # ── 3. Reconstruct in original order ──────────────────────────────────
        analyzed: List[dict] = []
        for seq_idx, sym, item in pending:
            nid = str(item.get("id") or "")
            result = results.get(seq_idx, _heuristic_analysis(item, sym))
            analyzed.append(
                {
                    "id": nid,
                    "symbol": sym,
                    "headline": item.get("headline") or item.get("title") or "",
                    "timestamp": item.get("timestamp") or now.isoformat(),
                    "label": result.get("label", "NEUTRAL"),
                    "strength": result.get("strength", 2),
                    "reason": result.get("reason", ""),
                    "confidence": result.get("confidence", 0.5),
                    "model": result.get("model", "RULE"),
                }
            )

        self._save_seen_ids(seen)
        return analyzed

    def _build_payload(self, analyzed: List[dict], symbols: List[str], now: Optional[datetime] = None) -> dict:
        ts = now or _utc_now()
        agg = self.aggregate_sentiment(analyzed)
        budget = self.get_budget_state(ts)
        return {
            "timestamp": ts.isoformat(),
            "batch_minutes": self.batch_minutes,
            "symbols": symbols,
            "items": analyzed,
            "news_sentiment_score": agg,
            "budget": {
                "daily_budget_usd": self.daily_budget_usd,
                "spent_usd": round(_safe_float(budget.get("spent_usd"), 0.0), 6),
                "calls": int(budget.get("calls", 0)),
                "estimated_tokens": int(budget.get("estimated_tokens", 0)),
            },
        }

    def run_batch(self, symbols: Iterable[str]) -> dict:
        now = _utc_now()
        cleaned_symbols = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
        if not cleaned_symbols:
            cleaned_symbols = ["BTC"]

        raw_items: List[dict] = []
        for sym in cleaned_symbols:
            raw_items.extend(collect_news_once(currencies=sym, limit=20))

        analyzed = self.analyze_news_items(raw_items, default_symbol=cleaned_symbols[0])
        payload = self._build_payload(analyzed, symbols=cleaned_symbols, now=now)

        self.save_batch(payload, now=now)
        return payload

    def run_stream(self, currencies: str = "BTC", duration_seconds: int = 300, poll_interval: float = 15.0) -> dict:
        """Consume Phase 9 news_stream and flush aggregated sentiment per batch window."""
        default_symbol = str(currencies or "BTC").split(",")[0].strip().upper() or "BTC"
        stream = NewsStream(currencies=currencies, poll_interval=max(1.0, poll_interval), limit=30)

        buffered_items: List[dict] = []
        outputs: List[dict] = []

        started_at = time.time()
        last_flush = started_at
        horizon = started_at + max(1, int(duration_seconds))

        while time.time() < horizon:
            try:
                fresh = stream.pump_once()
                if fresh:
                    buffered_items.extend(fresh)
            except Exception as exc:
                log.warning("news stream pump failed", error=exc)

            now_ts = time.time()
            if (now_ts - last_flush) >= self.batch_minutes * 60:
                batch_now = _utc_now()
                analyzed = self.analyze_news_items(buffered_items, default_symbol=default_symbol)
                buffered_items = []
                payload = self._build_payload(analyzed, symbols=[default_symbol], now=batch_now)
                self.save_batch(payload, now=batch_now)
                outputs.append(payload)
                last_flush = now_ts

            time.sleep(min(max(poll_interval, 1.0), 5.0))

        final_now = _utc_now()
        final_rows = self.analyze_news_items(buffered_items, default_symbol=default_symbol)
        final_payload = self._build_payload(final_rows, symbols=[default_symbol], now=final_now)
        self.save_batch(final_payload, now=final_now)
        outputs.append(final_payload)

        return {
            "ok": True,
            "mode": "stream",
            "duration_seconds": max(1, int(duration_seconds)),
            "batches": len(outputs),
            "latest": outputs[-1],
        }

    def save_batch(self, payload: dict, now: Optional[datetime] = None) -> Path:
        t = now or _utc_now()
        d = t.date().isoformat()
        ts = t.strftime("%H%M%S")
        out_dir = NEWS_ANALYSIS_DIR / d
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"batch-{ts}.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return p


def _cli() -> int:
    parser = argparse.ArgumentParser(description="News sentiment analyst")
    parser.add_argument("--symbols", default="BTC", help="comma-separated symbols")
    parser.add_argument("--budget", type=float, default=2.0)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--stream-seconds", type=int, default=0, help="run realtime stream mode for N seconds")
    parser.add_argument("--poll-interval", type=float, default=15.0)
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    analyst = NewsAnalyst(model=args.model, daily_budget_usd=args.budget)
    if args.stream_seconds > 0:
        out = analyst.run_stream(
            currencies=",".join(symbols) if symbols else "BTC",
            duration_seconds=args.stream_seconds,
            poll_interval=args.poll_interval,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        out = analyst.run_batch(symbols)
        print(json.dumps(out["news_sentiment_score"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
