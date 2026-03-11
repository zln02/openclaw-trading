"""Phase 18 monitoring/report module tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agents.alert_manager as alert_manager_mod
from agents.alert_manager import AlertManager
from agents.daily_report import DailyReportContext, DailyReportGenerator
from agents.weekly_report import WeeklyReportGenerator


class AlertManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        alert_manager_mod._COOLDOWN_DIR = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_alert_generation_and_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with patch("agents.alert_manager._COOLDOWN_DIR", Path(td)):
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

    def test_snapshot_file_merged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            snap = Path(td) / "snapshot.json"
            snap.write_text(
                json.dumps(
                    {
                        "drawdown": -0.05,
                        "var_95": 0.04,
                        "positions": [{"symbol": "AAPL", "market_value": 1000}],
                        "returns_252d": {"AAPL": [-0.01, 0.02, -0.03, 0.01, -0.02] * 60},
                    }
                ),
                encoding="utf-8",
            )
            mgr = AlertManager()
            payload = json.loads(snap.read_text(encoding="utf-8"))
            out = mgr.process(payload, send_telegram_alert=False)
            self.assertGreaterEqual(out["candidate_count"], 2)


class DailyReportTests(unittest.TestCase):
    def test_markdown_format(self) -> None:
        gen = DailyReportGenerator(supabase_client=None)
        text = gen.build_message(
            DailyReportContext(
                date_str="02/27",
                btc_pnl=120000,
                btc_pnl_pct=1.2,
                kr_pnl=30000,
                kr_pnl_pct=0.8,
                kr_mode="LIVE",
                us_pnl_usd=250.0,
                us_mode="LIVE",
                total_asset=12000000,
                total_pnl=150000,
                fg_value=55,
                fg_label="중립",
                composite_score=67,
                trend="UPTREND",
                info_snippets=["risk stable", "tomorrow reduce beta"],
            )
        )
        self.assertIn("일일 리포트", text)
        self.assertIn("BTC", text)


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
