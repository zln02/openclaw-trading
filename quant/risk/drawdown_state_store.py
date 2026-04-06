"""Supabase-backed persistent store for DrawdownGuardState.

Ensures drawdown guard state survives agent restarts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from common.logger import get_logger
from common.supabase_client import run_query_with_retry

log = get_logger("drawdown_state_store")

_TABLE = "drawdown_guard_state"


class DrawdownStateStore:
    """Load/save DrawdownGuardState to Supabase."""

    def load(self, market: str) -> dict:
        """Load persisted state for *market*.

        Returns:
            dict with keys: cooldown_until, last_action, triggered_rules.
            Empty defaults if no row exists.
        """
        defaults = {
            "cooldown_until": None,
            "last_action": "NONE",
            "triggered_rules": [],
        }

        def _query(sb):
            resp = (
                sb.table(_TABLE)
                .select("cooldown_until, last_action, triggered_rules")
                .eq("market", market.lower())
                .limit(1)
                .execute()
            )
            return resp.data

        rows = run_query_with_retry(_query, default=None)
        if not rows:
            return defaults

        row = rows[0]
        return {
            "cooldown_until": row.get("cooldown_until"),
            "last_action": row.get("last_action") or "NONE",
            "triggered_rules": row.get("triggered_rules") or [],
        }

    def save(self, market: str, state, triggered_rules: Optional[list] = None) -> bool:
        """Upsert state for *market*.

        Args:
            market: 'btc' | 'kr' | 'us'
            state: DrawdownGuardState instance (has cooldown_until, last_action)
            triggered_rules: list of triggered rule names
        """
        payload = {
            "market": market.lower(),
            "cooldown_until": getattr(state, "cooldown_until", None),
            "last_action": getattr(state, "last_action", "NONE"),
            "triggered_rules": triggered_rules or getattr(state, "triggered_rules", []),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        def _query(sb):
            return (
                sb.table(_TABLE)
                .upsert(payload, on_conflict="market")
                .execute()
            )

        result = run_query_with_retry(_query, default=None)
        if result is None:
            log.warning("drawdown state save failed", market=market)
            return False
        return True
