"""AI strategy layer agents (Phase 12 + Phase 14)."""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "StrategyReviewer",
    "NewsAnalyst",
    "RegimeClassifier",
    "AlertManager",
    "DailyReportGenerator",
    "WeeklyReportGenerator",
    "TradingAgentTeam",
]

_MODULE_BY_EXPORT = {
    "StrategyReviewer": "agents.strategy_reviewer",
    "NewsAnalyst": "agents.news_analyst",
    "RegimeClassifier": "agents.regime_classifier",
    "AlertManager": "agents.alert_manager",
    "DailyReportGenerator": "agents.daily_report",
    "WeeklyReportGenerator": "agents.weekly_report",
    "TradingAgentTeam": "agents.trading_agent_team",
}


def __getattr__(name: str) -> Any:
    module_name = _MODULE_BY_EXPORT.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name)
    return getattr(module, name)
