"""Weekly agent performance aggregation."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from common.logger import get_logger
from common.supabase_client import get_supabase

log = get_logger("agent_performance")


class AgentPerformanceTracker:
    @staticmethod
    async def evaluate_weekly(week_start: date | datetime, week_end: date | datetime) -> list[dict[str, Any]]:
        supabase = get_supabase()
        if not supabase:
            return []

        start_iso = week_start.isoformat()
        end_iso = week_end.isoformat()

        try:
            rows = await asyncio.to_thread(
                lambda: supabase.table("agent_decisions")
                .select("*")
                .gte("created_at", start_iso)
                .lte("created_at", end_iso)
                .execute()
                .data
                or []
            )
        except Exception as exc:
            log.warning("weekly performance load failed", error=str(exc))
            return []

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[(row.get("agent_name") or "unknown", row.get("market") or "btc")].append(row)

        summaries: list[dict[str, Any]] = []
        for (agent_name, market), items in grouped.items():
            signal_rows = [item for item in items if item.get("decision_type") in {"signal", "analysis", "conflict_resolution"}]
            total_signals = len(signal_rows)
            avg_confidence = round(
                sum(float(item.get("confidence") or 0) for item in signal_rows) / total_signals,
                4,
            ) if total_signals else 0.0
            veto_count = sum(1 for item in items if item.get("decision_type") == "conflict_resolution" and "veto" in str(item.get("reasoning", "")).lower())
            conflict_count = sum(1 for item in items if item.get("decision_type") == "conflict_resolution")
            correct_signals = sum(1 for item in signal_rows if str(item.get("result") or "").upper() in {"WIN", "CORRECT", "EXECUTED"})
            accuracy = round(correct_signals / total_signals, 4) if total_signals else None
            summary = {
                "period_start": start_iso[:10],
                "period_end": end_iso[:10],
                "agent_name": agent_name,
                "market": market,
                "total_signals": total_signals,
                "correct_signals": correct_signals,
                "accuracy": accuracy,
                "pnl_contribution": 0.0,
                "avg_confidence": avg_confidence,
                "veto_count": veto_count,
                "conflict_count": conflict_count,
            }
            summaries.append(summary)

        for summary in summaries:
            try:
                await asyncio.to_thread(lambda s=summary: supabase.table("agent_performance").insert(s).execute())
            except Exception as exc:
                log.warning("agent performance insert failed", error=str(exc), agent=summary["agent_name"])

        return summaries

    @staticmethod
    async def fetch_summary(period: str = "weekly") -> dict[str, Any]:
        supabase = get_supabase()
        if not supabase:
            return {"items": [], "period": period}

        try:
            rows = await asyncio.to_thread(
                lambda: supabase.table("agent_performance").select("*").order("created_at", desc=True).limit(30).execute().data or []
            )
            return {"items": rows, "period": period}
        except Exception as exc:
            log.warning("agent performance fetch failed", error=str(exc))
            return {"items": [], "period": period}


def current_week_window() -> tuple[date, date]:
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end
