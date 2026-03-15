"""Phase 14 BTC top-tier module tests."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import pandas as pd

from btc.signals.arb_detector import ArbitrageDetector, compute_kimchi_premium
from btc.signals.orderflow import analyze_trade_batch
from btc.signals.whale_tracker import classify_whale_activity
from btc.strategies.funding_carry import build_funding_carry_decision
from btc import btc_trading_agent as agent


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


class BtcTradingAgentSafetyTests(unittest.TestCase):
    def test_utc_now_iso_is_timezone_aware(self) -> None:
        self.assertTrue(agent._utc_now_iso().endswith("+00:00"))

    def test_has_valid_market_data_rejects_none(self) -> None:
        self.assertFalse(agent.has_valid_market_data(None))

    def test_candle_confirmation_requires_breakout_close(self) -> None:
        df = pd.DataFrame(
            [
                {"open": 100, "high": 105, "low": 99, "close": 104, "volume": 1},
                {"open": 104, "high": 112, "low": 103, "close": 111, "volume": 3},
                {"open": 111, "high": 113, "low": 110, "close": 112, "volume": 2},
            ]
        )

        out = agent.get_candle_confirmation(df)

        self.assertTrue(out["confirmed_breakout"])
        self.assertTrue(out["bullish_close"])
        self.assertTrue(out["close_near_high"])
        self.assertTrue(out["broke_prev_high"])

    def test_execute_trade_blocks_duplicate_buy_when_btc_balance_exists(self) -> None:
        signal = {"action": "BUY", "confidence": 80, "reason": "test"}
        indicators = {"price": 100_000_000, "atr": 500_000, "rsi": 50}

        with patch.object(agent.upbit, "get_balance", side_effect=[0.01, 1_000_000]), patch.object(
            agent, "get_open_position", return_value=None
        ):
            out = agent.execute_trade(
                signal,
                indicators,
                fg={"value": 20},
                volume={"ratio": 1.2},
                comp={"total": 70},
                candle_confirmation={"confirmed_breakout": True},
            )

        self.assertEqual(out["result"], "ALREADY_LONG")
        self.assertEqual(out["guard"], "already_long_block")

    def test_execute_trade_blocks_volume_spike_buy_without_confirmation(self) -> None:
        signal = {"action": "BUY", "confidence": 80, "reason": "test"}
        indicators = {"price": 100_000_000, "atr": 500_000, "rsi": 50}

        with patch.object(agent.upbit, "get_balance", side_effect=[0.0, 1_000_000]), patch.object(
            agent, "get_open_position", return_value=None
        ):
            out = agent.execute_trade(
                signal,
                indicators,
                fg={"value": 25},
                volume={"ratio": 3.4},
                comp={"total": 70},
                candle_confirmation={"confirmed_breakout": False},
            )

        self.assertEqual(out["result"], "BLOCKED_BREAKOUT_CONFIRMATION")
        self.assertEqual(out["guard"], "breakout_confirmation_block")

    def test_execute_trade_returns_sell_order_failed_on_trailing_stop_error(self) -> None:
        signal = {"action": "HOLD", "confidence": 80, "reason": "test"}
        indicators = {"price": 102_000_000, "atr": 500_000, "rsi": 50}
        pos = {
            "id": 1,
            "entry_price": 100_000_000,
            "highest_price": 105_000_000,
            "entry_time": "2026-03-16T00:00:00+00:00",
        }

        with patch.object(agent.upbit, "get_balance", side_effect=[0.01, 1_000_000]), patch.object(
            agent, "get_open_position", return_value=pos
        ), patch.object(agent, "_execute_sell_order", return_value=(False, "upbit_sell_error")):
            out = agent.execute_trade(signal, indicators)

        self.assertEqual(out["result"], "SELL_ORDER_FAILED")
        self.assertEqual(out["reason"], "upbit_sell_error")

    def test_run_trading_cycle_skips_on_missing_market_data(self) -> None:
        with patch.object(agent, "check_daily_loss", return_value=False), patch.object(
            agent, "get_market_data", return_value=None
        ):
            out = agent.run_trading_cycle()

        self.assertEqual(out["result"], "MARKET_DATA_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
