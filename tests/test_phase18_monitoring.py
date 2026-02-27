"""Phase 18 monitoring/report module tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents.alert_manager import AlertManager
from agents.daily_report import DailyReportContext, DailyReportGenerator
from agents.weekly_report import WeeklyReportGenerator


class AlertManagerTests(unittest.TestCase):
    def test_alert_generation_and_cooldown(self) -> None:
        mgr = AlertManager()
        snapshot = {
            "drawdown": -0.04,
            "var_95": 0.03,
            "corr_shift": 0.35,
            "volume_spike_ratio": 2.3,
        }

        first = mgr.process(snapshot, send_telegram_alert=False)
        second = mgr.process(snapshot, send_telegram_alert=False)

        self.assertGreaterEqual(first["candidate_count"], 3)
        self.assertGreater(first["emitted_count"], 0)
        self.assertEqual(second["emitted_count"], 0)  # dedupe cooldown


class DailyReportTests(unittest.TestCase):
    def test_markdown_format(self) -> None:
        gen = DailyReportGenerator(supabase_client=None)
        text = gen.build_markdown(
            DailyReportContext(
                today_pnl_pct=1.2,
                today_pnl_abs=120000,
                trade_count=8,
                wins=5,
                losses=3,
                tomorrow_strategy="Reduce high-beta exposure.",
                risk_status="STABLE",
            ),
            report_date="2026-02-27",
        )
        self.assertIn("Daily Trading Report", text)
        self.assertIn("Tomorrow Strategy", text)


class WeeklyReportTests(unittest.TestCase):
    def test_strategy_reviewer_summary_included(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            history_dir = Path(td)
            payload = {
                "next_strategy": {
                    "summary": "Favor low-volatility and positive cashflow names.",
                }
            }
            (history_dir / "2026-02-23.json").write_text(json.dumps(payload), encoding="utf-8")

            gen = WeeklyReportGenerator(strategy_history_dir=history_dir)
            ctx = gen.collect_context()
            report = gen.build_markdown(ctx, week_label="2026-W08")

            self.assertIn("Weekly Trading Report", report)
            self.assertIn("Strategy Reviewer", report)
            self.assertIn("Favor low-volatility", report)


if __name__ == "__main__":
    unittest.main()
