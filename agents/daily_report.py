"""Daily automatic report generator (Phase 18)."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram

load_env()
log = get_logger("daily_report")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _now_kst() -> datetime:
    # KST = UTC+9
    return datetime.now(timezone.utc).astimezone(timezone.utc).replace(tzinfo=None)


@dataclass
class DailyReportContext:
    today_pnl_pct: float
    today_pnl_abs: float
    trade_count: int
    wins: int
    losses: int
    tomorrow_strategy: str
    risk_status: str


class DailyReportGenerator:
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client or get_supabase()

    def should_send_now(self, as_of: Optional[datetime] = None, target_hour_kst: int = 21) -> bool:
        now = as_of or datetime.now()
        return now.hour == int(target_hour_kst)

    def build_markdown(self, ctx: DailyReportContext, report_date: Optional[str] = None) -> str:
        d = report_date or datetime.now().date().isoformat()
        win_rate = (ctx.wins / max(ctx.trade_count, 1)) * 100.0 if ctx.trade_count > 0 else 0.0

        return (
            f"## Daily Trading Report ({d})\n\n"
            f"- **Today PnL**: {ctx.today_pnl_pct:+.2f}% ({ctx.today_pnl_abs:+,.0f})\n"
            f"- **Trades**: {ctx.trade_count} (W {ctx.wins} / L {ctx.losses}, WinRate {win_rate:.1f}%)\n"
            f"- **Risk Status**: {ctx.risk_status}\n\n"
            f"### Tomorrow Strategy\n"
            f"{ctx.tomorrow_strategy}\n"
        )

    def collect_context(self) -> DailyReportContext:
        # Lightweight defaults to keep module independently runnable.
        today_pnl_pct = 0.0
        today_pnl_abs = 0.0
        trade_count = 0
        wins = 0
        losses = 0

        if self.supabase is not None:
            try:
                rows = (
                    self.supabase.table("trade_executions")
                    .select("pnl")
                    .order("created_at", desc=True)
                    .limit(200)
                    .execute()
                    .data
                    or []
                )
                pnls = [_safe_float(r.get("pnl"), 0.0) for r in rows]
                today_pnl_abs = sum(pnls)
                trade_count = len(pnls)
                wins = sum(1 for p in pnls if p > 0)
                losses = sum(1 for p in pnls if p < 0)
                base = 1000000.0
                today_pnl_pct = (today_pnl_abs / base) * 100.0
            except Exception as exc:
                log.warn("daily report supabase read failed", error=exc)

        risk_status = "STABLE" if today_pnl_pct > -3.0 else "CAUTION"
        tomorrow_strategy = "Follow regime-aware factor picks and execution router defaults."

        return DailyReportContext(
            today_pnl_pct=today_pnl_pct,
            today_pnl_abs=today_pnl_abs,
            trade_count=trade_count,
            wins=wins,
            losses=losses,
            tomorrow_strategy=tomorrow_strategy,
            risk_status=risk_status,
        )

    def run(self, send: bool = True) -> dict:
        ctx = self.collect_context()
        text = self.build_markdown(ctx)

        sent = False
        if send:
            sent = send_telegram(text, parse_mode="Markdown")

        return {
            "ok": True,
            "sent": bool(sent),
            "report": text,
            "context": ctx.__dict__,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Daily report generator")
    parser.add_argument("--no-send", action="store_true")
    args = parser.parse_args()

    out = DailyReportGenerator().run(send=not args.no_send)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
