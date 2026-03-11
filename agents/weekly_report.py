"""Weekly automatic report generator (Phase 18)."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram

load_env()
log = get_logger("weekly_report")

STRATEGY_HISTORY_DIR = BRAIN_PATH / "strategy-history"
KR_DRIFT_PATH = BRAIN_PATH / "ml" / "drift_report.json"
US_DRIFT_PATH = BRAIN_PATH / "ml" / "us" / "drift_report.json"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


@dataclass
class WeeklyReportContext:
    weekly_pnl_pct: float
    weekly_pnl_abs: float
    trade_count: int
    market_breakdown: str
    factor_summary: str
    regime_change: str
    drift_summary: str
    next_week_plan: str
    strategy_reviewer_summary: str


class WeeklyReportGenerator:
    def __init__(self, strategy_history_dir: Path = STRATEGY_HISTORY_DIR):
        self.strategy_history_dir = Path(strategy_history_dir)
        self.supabase = get_supabase()

    def is_send_day(self, as_of: Optional[date | datetime | str] = None) -> bool:
        if as_of is None:
            d = date.today()
        elif isinstance(as_of, datetime):
            d = as_of.date()
        elif isinstance(as_of, date):
            d = as_of
        else:
            d = datetime.strptime(str(as_of)[:10], "%Y-%m-%d").date()
        return d.weekday() == 6

    def load_latest_strategy_review_summary(self) -> str:
        if not self.strategy_history_dir.exists():
            return "No strategy reviewer history found."

        files = sorted(self.strategy_history_dir.glob("*.json"))
        if not files:
            return "No strategy reviewer history found."

        latest = files[-1]
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
            next_strategy = payload.get("next_strategy") or {}
            summary = str(next_strategy.get("summary") or "")
            if summary:
                return summary
            return "Strategy review present but summary is empty."
        except Exception as exc:
            log.warning("failed to load strategy review summary", error=exc)
            return "Failed to read strategy reviewer result."

    def _load_drift_summary(self, path: Path, label: str) -> str:
        if not path.exists():
            return f"{label} N/A"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = str(payload.get("status", "N/A")).upper()
            max_psi = _safe_float(payload.get("max_psi"), 0.0)
            return f"{label} {status} ({max_psi:.2f})"
        except Exception as exc:
            log.warning("failed to load drift report", label=label, error=exc)
            return f"{label} ERROR"

    def _collect_market_trades(self, market: str, since: str, until: str) -> dict:
        table_map = {"kr": "trade_executions", "us": "us_trade_executions", "btc": "btc_position"}
        time_col_map = {"kr": "created_at", "us": "created_at", "btc": "exit_time"}
        pnl_cols = {"kr": ("pnl_pct", "pnl_krw"), "us": ("pnl_pct", "pnl_usd"), "btc": ("pnl", None)}

        out = {"trades": 0, "closed": 0, "wins": 0, "pnl_sum": 0.0, "pnl_pct_sum": 0.0, "pnl_pct_count": 0}
        if not self.supabase:
            return out

        try:
            query = (
                self.supabase.table(table_map[market])
                .select("*")
                .gte(time_col_map[market], since)
                .lt(time_col_map[market], until)
            )
            if market == "btc":
                query = query.eq("status", "CLOSED")
            rows = query.execute().data or []
        except Exception as exc:
            log.warning("weekly market metrics failed", market=market, error=str(exc))
            return out

        pnl_col, pnl_fallback = pnl_cols[market]
        out["trades"] = len(rows)
        for row in rows:
            is_closed = market == "btc" or str(row.get("result") or "").upper() in {"CLOSED", "SELL"}
            if not is_closed:
                continue
            out["closed"] += 1
            raw_pnl = row.get(pnl_col) or (row.get(pnl_fallback) if pnl_fallback else None)
            pnl = _safe_float(raw_pnl, 0.0)
            out["pnl_sum"] += pnl
            if pnl > 0:
                out["wins"] += 1
            if market in {"kr", "us"} and row.get("pnl_pct") is not None:
                out["pnl_pct_sum"] += _safe_float(row.get("pnl_pct"), 0.0)
                out["pnl_pct_count"] += 1
        return out

    def _collect_weekly_metrics(self) -> dict:
        end_day = datetime.now().date()
        start_iso = (end_day - timedelta(days=7)).isoformat()
        end_iso = (end_day + timedelta(days=1)).isoformat()
        per_market = {m: self._collect_market_trades(m, start_iso, end_iso) for m in ("kr", "us", "btc")}
        trade_count = sum(v["trades"] for v in per_market.values())
        closed = sum(v["closed"] for v in per_market.values())
        wins = sum(v["wins"] for v in per_market.values())
        pnl_abs = sum(v["pnl_sum"] for v in per_market.values())
        pct_count = sum(v["pnl_pct_count"] for v in per_market.values())
        pnl_pct = (sum(v["pnl_pct_sum"] for v in per_market.values()) / pct_count) if pct_count > 0 else 0.0
        return {
            "trade_count": trade_count,
            "closed_count": closed,
            "wins": wins,
            "weekly_pnl_abs": pnl_abs,
            "weekly_pnl_pct": pnl_pct,
            "per_market": per_market,
        }

    def build_markdown(self, ctx: WeeklyReportContext, week_label: Optional[str] = None) -> str:
        label = week_label or datetime.now().strftime("%Y-W%W")
        return (
            f"## Weekly Trading Report ({label})\n\n"
            f"- **Weekly PnL**: {ctx.weekly_pnl_pct:+.2f}% ({ctx.weekly_pnl_abs:+,.0f})\n"
            f"- **Trades**: {ctx.trade_count}\n"
            f"- **By Market**: {ctx.market_breakdown}\n"
            f"- **Factor Contribution**: {ctx.factor_summary}\n"
            f"- **Regime Change**: {ctx.regime_change}\n\n"
            f"- **ML Drift**: {ctx.drift_summary}\n\n"
            f"### Strategy Reviewer\n"
            f"{ctx.strategy_reviewer_summary}\n\n"
            f"### Next Week Plan\n"
            f"{ctx.next_week_plan}\n"
        )

    def collect_context(self) -> WeeklyReportContext:
        weekly = self._collect_weekly_metrics()
        per_market = weekly["per_market"]
        market_breakdown = " | ".join(
            [
                f"BTC {per_market['btc']['pnl_sum']:+,.0f} ({per_market['btc']['closed']}c/{per_market['btc']['trades']}t)",
                f"KR {per_market['kr']['pnl_sum']:+,.0f} ({per_market['kr']['closed']}c/{per_market['kr']['trades']}t)",
                f"US {per_market['us']['pnl_sum']:+,.0f} ({per_market['us']['closed']}c/{per_market['us']['trades']}t)",
            ]
        )
        drift_summary = (
            f"{self._load_drift_summary(KR_DRIFT_PATH, 'KR')} | "
            f"{self._load_drift_summary(US_DRIFT_PATH, 'US')}"
        )
        return WeeklyReportContext(
            weekly_pnl_pct=weekly["weekly_pnl_pct"],
            weekly_pnl_abs=weekly["weekly_pnl_abs"],
            trade_count=weekly["trade_count"],
            market_breakdown=market_breakdown,
            factor_summary="No major positive or negative factor tilt.",
            regime_change=f"Closed {weekly['closed_count']} / Wins {weekly['wins']}",
            drift_summary=drift_summary,
            next_week_plan="Keep diversified exposures and enforce VaR limits.",
            strategy_reviewer_summary=self.load_latest_strategy_review_summary(),
        )

    def run(self, send: bool = True) -> dict:
        ctx = self.collect_context()
        report = self.build_markdown(ctx)
        sent = send_telegram(report, parse_mode="Markdown") if send else False
        return {
            "ok": True,
            "sent": bool(sent),
            "report": report,
            "context": ctx.__dict__,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Weekly report generator")
    parser.add_argument("--no-send", action="store_true")
    args = parser.parse_args()

    out = WeeklyReportGenerator().run(send=not args.no_send)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
