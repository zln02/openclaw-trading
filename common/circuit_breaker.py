"""Portfolio-level circuit breaker and emergency guards."""
from __future__ import annotations

import asyncio
from typing import Any

from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram

log = get_logger("circuit_breaker")
_PERSIST_WARNED = False  # circuit_breaker_events 테이블 없음 경고 1회만 출력

import time as _time
_TELEGRAM_COOLDOWN = 86400  # 24시간 — 같은 레벨 알림 중복 방지
_last_telegram_ts: dict[str, float] = {}  # level → 마지막 발송 시각


class CircuitBreaker:
    LEVELS = {
        "WARNING": {"threshold": -0.15, "action": "alert_only"},
        "HALT": {"threshold": -0.25, "action": "block_new_buys"},
        "EMERGENCY": {"threshold": -0.35, "action": "liquidate_all"},
    }

    def __init__(self) -> None:
        self.is_halted = False

    async def check(self, portfolio_state: dict[str, Any]) -> dict[str, Any]:
        drawdown = float(portfolio_state.get("current_drawdown") or 0.0)

        for level_name, config in self.LEVELS.items():
            if drawdown <= config["threshold"]:
                await self._trigger(level_name, drawdown, config["action"], portfolio_state)
                if config["action"] == "block_new_buys":
                    self.is_halted = True
                    return {"allowed": False, "reason": f"Circuit breaker: {level_name}", "level": level_name}
                if config["action"] == "liquidate_all":
                    await self._emergency_liquidation(portfolio_state)
                    return {"allowed": False, "reason": "EMERGENCY LIQUIDATION", "level": level_name}

        return {"allowed": True, "level": "NORMAL", "drawdown": drawdown}

    async def _trigger(self, level: str, drawdown: float, action: str, details: dict[str, Any] | None = None) -> None:
        supabase = get_supabase()
        payload = {
            "trigger_level": level,
            "portfolio_drawdown": drawdown,
            "action_taken": action,
            "details": details or {},
        }
        if supabase:
            try:
                await asyncio.to_thread(
                    lambda: supabase.table("circuit_breaker_events").insert(payload).execute()
                )
            except Exception as exc:
                global _PERSIST_WARNED
                if not _PERSIST_WARNED:
                    log.warning("circuit breaker persist failed (이후 동일 오류 무시)", error=str(exc))
                    _PERSIST_WARNED = True

        emoji = {"WARNING": "⚠️", "HALT": "🛑", "EMERGENCY": "🚨"}.get(level, "⚠️")
        global _last_telegram_ts
        now = _time.monotonic()
        if now - _last_telegram_ts.get(level, 0) >= _TELEGRAM_COOLDOWN:
            _last_telegram_ts[level] = now
            await asyncio.to_thread(
                send_telegram,
                f"{emoji} CIRCUIT BREAKER: {level}\nPortfolio Drawdown: {drawdown:.1%}\nAction: {action}",
            )

    async def _emergency_liquidation(self, details: dict[str, Any] | None = None) -> None:
        await asyncio.to_thread(send_telegram, "🚨 EMERGENCY: 전량 청산 실행 중...")
        log.critical("emergency liquidation requested", details=details or {})


def _compute_drawdown_from_pnl(pnl_series: list[float]) -> float:
    if not pnl_series:
        return 0.0
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for pnl_pct in pnl_series:
        equity *= 1.0 + (float(pnl_pct) / 100.0)
        peak = max(peak, equity)
        drawdown = (equity - peak) / peak
        worst = min(worst, drawdown)
    return worst


def build_portfolio_state_sync(market: str) -> dict[str, Any]:
    supabase = get_supabase()
    if not supabase:
        return {"market": market, "current_drawdown": 0.0, "source": "no_supabase"}

    market_key = market.lower()
    if market_key == "btc":
        source_table = "btc_position"
    elif market_key == "kr":
        source_table = "trade_executions"
    else:
        source_table = "us_trade_executions"

    def _run_query():
        if market_key == "btc":
            return supabase.table(source_table).select("pnl_pct").eq("status", "CLOSED").order("exit_time", desc=True).limit(200).execute()
        elif market_key == "kr":
            return supabase.table(source_table).select("pnl_pct").eq("result", "CLOSED").order("created_at", desc=True).limit(200).execute()
        else:
            return supabase.table(source_table).select("pnl_pct").eq("result", "CLOSED").order("created_at", desc=True).limit(200).execute()

    try:
        rows = _run_query().data or []
    except Exception as exc:
        log.warning("drawdown state load failed", market=market, error=str(exc))
        rows = []

    pnl_series = [float(row.get("pnl_pct") or 0.0) for row in reversed(rows)]
    drawdown = _compute_drawdown_from_pnl(pnl_series)
    return {
        "market": market_key,
        "current_drawdown": drawdown,
        "closed_trades": len(rows),
        "source_table": source_table,
    }


def check_trade_allowed_sync(market: str, portfolio_state: dict[str, Any] | None = None) -> dict[str, Any]:
    breaker = CircuitBreaker()
    state = portfolio_state or build_portfolio_state_sync(market)
    return asyncio.run(breaker.check(state))
