"""Structured agent decision logging."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from common.logger import get_logger
from common.supabase_client import get_supabase

log = get_logger("decision_logger")


class DecisionLogger:
    @staticmethod
    async def log(
        agent_name: str,
        market: str,
        decision_type: str,
        action: str,
        reasoning: str,
        confidence: float | None = None,
        context: dict[str, Any] | None = None,
        result: str | None = None,
    ) -> dict[str, Any]:
        supabase = get_supabase()
        row = {
            "agent_name": agent_name,
            "market": market,
            "decision_type": decision_type,
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning[:4000],
            "context": context or {},
            "result": result,
        }
        if not supabase:
            return {"ok": False, "reason": "supabase_unavailable", "row": row}
        try:
            await asyncio.to_thread(lambda: supabase.table("agent_decisions").insert(row).execute())
            return {"ok": True, "row": row}
        except Exception as exc:
            log.warning("decision log insert failed", error=str(exc), agent_name=agent_name, market=market)
            return {"ok": False, "reason": str(exc), "row": row}

    @staticmethod
    def log_sync(
        agent_name: str,
        market: str,
        decision_type: str,
        action: str,
        reasoning: str,
        confidence: float | None = None,
        context: dict[str, Any] | None = None,
        result: str | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(
            DecisionLogger.log(
                agent_name=agent_name,
                market=market,
                decision_type=decision_type,
                action=action,
                reasoning=reasoning,
                confidence=confidence,
                context=context,
                result=result,
            )
        )
