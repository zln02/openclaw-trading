"""Phase 16 US top-tier module tests."""
from __future__ import annotations

import unittest

from stocks.signals.earnings_model import EarningsSurpriseModel, compute_sue
from stocks.signals.options_flow import analyze_options_flow
from stocks.signals.sec_13f import compare_13f_holdings
from stocks.signals.short_interest import evaluate_short_interest
from stocks.us_broker import AlpacaBroker


class USBrokerTests(unittest.TestCase):
    def test_alpaca_route_and_execute_simulated(self) -> None:
        broker = AlpacaBroker(live=False, api_key="", secret_key="")
        out = broker.route_and_execute("AAPL", "buy", 2, price_hint=180.0, simulate=True)
        self.assertTrue(out["ok"])
        self.assertEqual(out["broker_mode"], "paper")
        self.assertIn("decision", out)


class SEC13FTests(unittest.TestCase):
    def test_compare_13f_holdings_detects_changes(self) -> None:
        prev_rows = [
            {"symbol": "AAPL", "shares": 100},
            {"symbol": "MSFT", "shares": 80},
            {"symbol": "TSLA", "shares": 40},
        ]
        curr_rows = [
            {"symbol": "AAPL", "shares": 130},   # ADD
            {"symbol": "MSFT", "shares": 50},    # REDUCE
            {"symbol": "NVDA", "shares": 70},    # NEW
        ]
        changes = compare_13f_holdings(prev_rows, curr_rows, fund_name="SampleFund")
        by_symbol = {c["symbol"]: c["change_type"] for c in changes}
        self.assertEqual(by_symbol["AAPL"], "ADD")
        self.assertEqual(by_symbol["MSFT"], "REDUCE")
        self.assertEqual(by_symbol["NVDA"], "NEW")
        self.assertEqual(by_symbol["TSLA"], "EXIT")


class OptionsFlowTests(unittest.TestCase):
    def test_unusual_call_activity_bullish(self) -> None:
        out = analyze_options_flow(
            symbol="NVDA",
            call_volume=120000,
            put_volume=45000,
            avg_call_volume=40000,
            avg_put_volume=40000,
            prev_put_call_ratio=1.2,
            call_notional=3000000,
            put_notional=900000,
        )
        self.assertTrue(out["unusual_call"])
        self.assertEqual(out["bias"], "BULLISH")


class EarningsModelTests(unittest.TestCase):
    def test_compute_sue(self) -> None:
        sue = compute_sue(actual_eps=1.40, consensus_eps=1.10, surprise_std=0.15)
        self.assertAlmostEqual(sue, 2.0, places=6)

    def test_predict_bullish_drift(self) -> None:
        model = EarningsSurpriseModel()
        model.fit([
            {"sue": 1.0, "drift_3d_pct": 1.8},
            {"sue": 0.7, "drift_3d_pct": 1.2},
            {"sue": -0.8, "drift_3d_pct": -1.1},
        ])
        out = model.predict("AAPL", actual_eps=1.5, consensus_eps=1.0, surprise_std=0.2)
        self.assertEqual(out["direction"], "BULLISH")
        self.assertGreater(out["expected_drift_3d_pct"], 0)


class ShortInterestTests(unittest.TestCase):
    def test_squeeze_candidate_detection(self) -> None:
        out = evaluate_short_interest("GME", short_interest_pct=25.0, days_to_cover=6.5, price_change_5d_pct=4.2)
        self.assertTrue(out["squeeze_candidate"])
        self.assertEqual(out["risk_level"], "HIGH")


if __name__ == "__main__":
    unittest.main()
