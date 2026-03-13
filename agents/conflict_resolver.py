"""Structured conflict resolution for multi-agent decisions."""
from __future__ import annotations


class ConflictResolver:
    PRIORITY = {
        "risk_manager": 3,
        "market_analyst": 2,
        "news_analyst": 1,
    }

    @staticmethod
    def resolve(decisions: list[dict]) -> dict:
        risk_manager_vote = next((item for item in decisions if item.get("agent") == "risk_manager"), None)
        if (
            risk_manager_vote
            and risk_manager_vote.get("action") in {"HOLD", "SELL", "SKIP"}
            and float(risk_manager_vote.get("confidence") or 0) >= 0.6
        ):
            return {
                "action": risk_manager_vote["action"],
                "reason": f"Risk Manager veto: {risk_manager_vote.get('reasoning', '')}",
                "conflict": True,
                "weighted_scores": {risk_manager_vote["action"]: risk_manager_vote.get("confidence", 0)},
            }

        weighted_scores: dict[str, float] = {}
        for item in decisions:
            action = str(item.get("action") or "HOLD").upper()
            weight = self_weight = ConflictResolver.PRIORITY.get(item.get("agent", ""), 1) * float(item.get("confidence") or 0.5)
            weighted_scores[action] = weighted_scores.get(action, 0.0) + self_weight

        winner = max(weighted_scores, key=weighted_scores.get) if weighted_scores else "HOLD"
        return {
            "action": winner,
            "reason": f"Weighted vote: {weighted_scores}",
            "conflict": len({str(item.get('action') or 'HOLD').upper() for item in decisions}) > 1,
            "weighted_scores": weighted_scores,
        }
