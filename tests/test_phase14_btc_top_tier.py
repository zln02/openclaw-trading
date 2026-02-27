"""Phase 14 BTC top-tier module tests."""
from __future__ import annotations

import time
import unittest

from btc.signals.arb_detector import ArbitrageDetector, compute_kimchi_premium
from btc.signals.orderflow import analyze_trade_batch
from btc.signals.whale_tracker import classify_whale_activity
from btc.strategies.funding_carry import build_funding_carry_decision


class OrderFlowTests(unittest.TestCase):
    def test_cvd_and_large_trade_counts(self) -> None:
        base_ms = int(time.time() * 1000)
        trades = [
            {"q": "5", "m": False, "T": base_ms},  # aggressive buy
            {"q": "12", "m": False, "T": base_ms + 1_000},  # large buy
            {"q": "11", "m": True, "T": base_ms + 2_000},  # large sell
            {"q": "1", "m": True, "T": base_ms + 3_000},
        ]
        out = analyze_trade_batch(trades, large_trade_threshold_btc=10.0, window_seconds=60)

        self.assertAlmostEqual(out["cvd"], 5.0, places=6)  # +5 +12 -11 -1
        self.assertEqual(out["large_buy_count"], 1)
        self.assertEqual(out["large_sell_count"], 1)
        self.assertAlmostEqual(out["net_flow"], 5.0, places=6)


class FundingCarryTests(unittest.TestCase):
    def test_positive_funding_triggers_short_perp_carry(self) -> None:
        out = build_funding_carry_decision(0.08)
        self.assertEqual(out["action"], "CARRY_SHORT_PERP")
        self.assertEqual(out["spot_side"], "BUY")
        self.assertEqual(out["futures_side"], "SELL")

    def test_negative_funding_triggers_long_perp_carry(self) -> None:
        out = build_funding_carry_decision(-0.05)
        self.assertEqual(out["action"], "CARRY_LONG_PERP")
        self.assertEqual(out["spot_side"], "SELL")
        self.assertEqual(out["futures_side"], "BUY")


class ArbitrageTests(unittest.TestCase):
    def test_kimchi_premium_formula(self) -> None:
        premium = compute_kimchi_premium(150_000_000, 100_000, 1_300)
        # fair KRW = 130,000,000, premium about +15.3846%
        self.assertAlmostEqual(premium, 15.384615, places=4)

    def test_detector_reverse_premium_signal(self) -> None:
        detector = ArbitrageDetector(premium_alert_pct=5.0, reverse_premium_pct=-1.0)
        out = detector.detect(upbit_price_krw=120_000_000, binance_price_usdt=100_000, usd_krw=1300)
        self.assertEqual(out["state"], "REVERSE_PREMIUM")
        self.assertGreater(out["signal_boost"], 0)


class WhaleTrackerTests(unittest.TestCase):
    def test_sell_pressure_classification(self) -> None:
        out = classify_whale_activity(
            inflow_btc=4000,
            outflow_btc=1000,
            inflow_avg_btc=1800,
            outflow_avg_btc=1200,
            lth_moved_btc=100,
            lth_avg_btc=120,
        )
        self.assertEqual(out["signal"], "SELL_PRESSURE")
        self.assertLess(out["pressure_score"], 0)

    def test_hodl_signal_classification(self) -> None:
        out = classify_whale_activity(
            inflow_btc=1000,
            outflow_btc=3500,
            inflow_avg_btc=1200,
            outflow_avg_btc=1500,
            lth_moved_btc=100,
            lth_avg_btc=120,
        )
        self.assertEqual(out["signal"], "HODL_SIGNAL")
        self.assertGreater(out["pressure_score"], 0)


if __name__ == "__main__":
    unittest.main()
