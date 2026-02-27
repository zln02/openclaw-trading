"""Rule-based drawdown guard (Phase 11).

Rules:
- daily loss > 2%  -> block new buys
- weekly loss > 5% -> reduce positions by 50%
- monthly loss > 10% -> force liquidation + cooldown 7 days
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("risk_dd_guard")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_date(value: str | date | datetime | None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return datetime.now().date()
    text = str(value).strip()[:10]
    return datetime.strptime(text, "%Y-%m-%d").date()


@dataclass
class DrawdownGuardConfig:
    daily_loss_limit: float = -0.02
    weekly_loss_limit: float = -0.05
    monthly_loss_limit: float = -0.10
    weekly_reduce_ratio: float = 0.50
    cooldown_days: int = 7


@dataclass
class DrawdownGuardState:
    cooldown_until: Optional[str] = None
    last_action: str = "NONE"


class DrawdownGuard:
    def __init__(self, config: Optional[DrawdownGuardConfig] = None):
        self.config = config or DrawdownGuardConfig()

    def evaluate(
        self,
        daily_return: float,
        weekly_return: float,
        monthly_return: float,
        as_of: str | date | datetime | None = None,
        state: Optional[DrawdownGuardState] = None,
    ) -> dict:
        now = _to_date(as_of)
        state = state or DrawdownGuardState()

        decision = {
            "as_of": now.isoformat(),
            "allow_new_buys": True,
            "reduce_positions_ratio": 0.0,
            "force_liquidate": False,
            "cooldown_until": state.cooldown_until,
            "triggered_rules": [],
            "daily_return": _safe_float(daily_return),
            "weekly_return": _safe_float(weekly_return),
            "monthly_return": _safe_float(monthly_return),
        }

        # cooldown check first
        if state.cooldown_until:
            try:
                c_until = _to_date(state.cooldown_until)
                if now <= c_until:
                    decision["allow_new_buys"] = False
                    decision["triggered_rules"].append("COOLDOWN_ACTIVE")
            except Exception:
                pass

        d = _safe_float(daily_return)
        w = _safe_float(weekly_return)
        m = _safe_float(monthly_return)

        # severity order: monthly > weekly > daily
        if m <= self.config.monthly_loss_limit:
            decision["allow_new_buys"] = False
            decision["force_liquidate"] = True
            decision["reduce_positions_ratio"] = 1.0
            c_until = now + timedelta(days=max(self.config.cooldown_days, 1))
            decision["cooldown_until"] = c_until.isoformat()
            decision["triggered_rules"].append("MONTHLY_STOP")
        elif w <= self.config.weekly_loss_limit:
            decision["allow_new_buys"] = False
            decision["reduce_positions_ratio"] = max(0.0, min(1.0, self.config.weekly_reduce_ratio))
            decision["triggered_rules"].append("WEEKLY_DELEVERAGE")
        elif d <= self.config.daily_loss_limit:
            decision["allow_new_buys"] = False
            decision["triggered_rules"].append("DAILY_BUY_BLOCK")

        decision["state"] = self.next_state(state, decision)
        return decision

    def next_state(self, prev: DrawdownGuardState, decision: dict) -> DrawdownGuardState:
        triggers = decision.get("triggered_rules") or []
        if "MONTHLY_STOP" in triggers:
            return DrawdownGuardState(
                cooldown_until=decision.get("cooldown_until"),
                last_action="MONTHLY_STOP",
            )
        if "WEEKLY_DELEVERAGE" in triggers:
            return DrawdownGuardState(
                cooldown_until=prev.cooldown_until,
                last_action="WEEKLY_DELEVERAGE",
            )
        if "DAILY_BUY_BLOCK" in triggers:
            return DrawdownGuardState(
                cooldown_until=prev.cooldown_until,
                last_action="DAILY_BUY_BLOCK",
            )
        if "COOLDOWN_ACTIVE" in triggers:
            return DrawdownGuardState(
                cooldown_until=prev.cooldown_until,
                last_action="COOLDOWN_ACTIVE",
            )
        return DrawdownGuardState(
            cooldown_until=prev.cooldown_until,
            last_action="NONE",
        )

    def returns_from_equity_curve(
        self,
        equity_curve: Sequence[dict],
        as_of: str | date | datetime | None = None,
    ) -> dict:
        """Compute daily/weekly/monthly returns from date-sorted equity curve.

        equity_curve item format:
        {"date": "YYYY-MM-DD", "equity": 12345.6}
        """
        if not equity_curve:
            return {"daily_return": 0.0, "weekly_return": 0.0, "monthly_return": 0.0}

        now = _to_date(as_of)
        rows = sorted(
            [
                {"date": _to_date(r.get("date")), "equity": _safe_float(r.get("equity"), 0.0)}
                for r in equity_curve
                if _safe_float(r.get("equity"), 0.0) > 0
            ],
            key=lambda x: x["date"],
        )
        if not rows:
            return {"daily_return": 0.0, "weekly_return": 0.0, "monthly_return": 0.0}

        latest = None
        for r in rows:
            if r["date"] <= now:
                latest = r
            else:
                break
        if latest is None:
            latest = rows[-1]

        def _equity_on_or_before(target: date) -> Optional[float]:
            val = None
            for r in rows:
                if r["date"] <= target:
                    val = r["equity"]
                else:
                    break
            return val

        cur_eq = latest["equity"]
        prev_d = _equity_on_or_before(now - timedelta(days=1))
        prev_w = _equity_on_or_before(now - timedelta(days=7))
        prev_m = _equity_on_or_before(now - timedelta(days=30))

        def _ret(prev: Optional[float]) -> float:
            if prev is None or prev <= 0:
                return 0.0
            return cur_eq / prev - 1.0

        return {
            "daily_return": round(_ret(prev_d), 6),
            "weekly_return": round(_ret(prev_w), 6),
            "monthly_return": round(_ret(prev_m), 6),
        }


if __name__ == "__main__":
    guard = DrawdownGuard()
    state = DrawdownGuardState()
    decision = guard.evaluate(
        daily_return=-0.012,
        weekly_return=-0.033,
        monthly_return=-0.108,
        state=state,
    )
    log.info("drawdown_guard", triggered=decision.get("triggered_rules"), cooldown=decision.get("cooldown_until"))
