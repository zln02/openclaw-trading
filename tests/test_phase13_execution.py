"""Phase 13 execution module tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execution.slippage_tracker import ExecutionFill, SlippageTracker, compute_slippage_metrics
from execution.smart_router import RouterConfig, SmartRouter
from execution.twap import TWAPOrder, build_twap_schedule
from execution.vwap import VWAPOrder, build_vwap_schedule


class TWAPTests(unittest.TestCase):
    def test_twap_schedule_preserves_total_qty(self) -> None:
        order = TWAPOrder(symbol="BTC", side="buy", total_qty=1.25, duration_minutes=10, market="btc")
        schedule = build_twap_schedule(order)

        qty_sum = sum(float(s.get("qty", 0.0)) for s in schedule.get("slices", []))
        self.assertGreater(len(schedule.get("slices", [])), 0)
        self.assertAlmostEqual(qty_sum, 1.25, places=6)

    def test_twap_kr_schedule_uses_integer_shares(self) -> None:
        order = TWAPOrder(symbol="005930", side="buy", total_qty=7, duration_minutes=30, market="kr")
        schedule = build_twap_schedule(order)

        slices = schedule.get("slices", [])
        qtys = [float(s.get("qty", 0.0)) for s in slices]
        self.assertLessEqual(len(slices), 7)
        self.assertEqual(sum(int(q) for q in qtys), 7)
        self.assertTrue(all(abs(q - round(q)) < 1e-9 for q in qtys))


class VWAPTests(unittest.TestCase):
    def test_vwap_schedule_preserves_weights_and_total_qty(self) -> None:
        order = VWAPOrder(symbol="BTC", side="buy", total_qty=2.0, duration_minutes=60, market="btc", buckets=5)
        schedule = build_vwap_schedule(order, profile=[0.1, 0.2, 0.4, 0.2, 0.1])

        weights = schedule.get("weights", [])
        qty_sum = sum(float(b.get("qty", 0.0)) for b in schedule.get("buckets", []))

        self.assertEqual(len(weights), 5)
        self.assertAlmostEqual(sum(weights), 1.0, places=6)
        self.assertAlmostEqual(qty_sum, 2.0, places=6)

    def test_vwap_kr_schedule_uses_integer_shares(self) -> None:
        order = VWAPOrder(symbol="005930", side="sell", total_qty=9, duration_minutes=50, market="kr", buckets=20)
        schedule = build_vwap_schedule(order, profile=[1.0] * 20)

        buckets = schedule.get("buckets", [])
        qtys = [float(b.get("qty", 0.0)) for b in buckets]

        self.assertLessEqual(len(buckets), 9)
        self.assertEqual(sum(int(q) for q in qtys), 9)
        self.assertTrue(all(abs(q - round(q)) < 1e-9 for q in qtys))


class SlippageTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tracker = SlippageTracker(
            supabase_client=None,
            local_dir=Path(self.tmp.name),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_compute_slippage_buy(self) -> None:
        metrics = compute_slippage_metrics(expected_price=100, actual_price=101, side="buy")
        self.assertTrue(metrics["is_valid"])
        self.assertAlmostEqual(metrics["slippage_bps"], 100.0, places=6)
        self.assertAlmostEqual(metrics["adverse_slippage_bps"], 100.0, places=6)

    def test_track_and_monthly_report_local(self) -> None:
        row = self.tracker.track_fill(
            ExecutionFill(
                symbol="BTC",
                side="buy",
                qty=0.1,
                expected_price=100.0,
                actual_price=100.2,
                market="btc",
                route="TWAP",
            ),
            persist_db=False,
        )

        ym = str(row.get("timestamp", ""))[:7]
        report = self.tracker.monthly_report(year_month=ym)

        self.assertEqual(report["trade_count"], 1)
        self.assertGreaterEqual(report["avg_abs_slippage_bps"], 0.0)
        self.assertIn("route_stats", report)


class SmartRouterTests(unittest.TestCase):
    def test_decide_route_by_notional(self) -> None:
        cfg = RouterConfig(
            small_notional_threshold_usd=100.0,
            medium_notional_threshold_usd=500.0,
            narrow_spread_bps=8.0,
            wide_spread_bps=25.0,
            track_slippage=False,
        )
        router = SmartRouter(config=cfg)

        with patch.object(router, "_get_reference_price", return_value=10.0), patch.object(
            router,
            "_get_spread_bps",
            return_value=5.0,
        ):
            d_small = router.decide("AAPL", "buy", 8, market="auto")   # notional 80
            d_mid = router.decide("AAPL", "buy", 30, market="auto")    # notional 300
            d_large = router.decide("AAPL", "buy", 100, market="auto")  # notional 1000

        self.assertEqual(d_small.market, "us")
        self.assertEqual(d_small.route, "MARKET")
        self.assertEqual(d_mid.route, "TWAP")
        self.assertEqual(d_large.route, "VWAP")

    def test_auto_market_inference_for_kr_symbol(self) -> None:
        cfg = RouterConfig(track_slippage=False)
        router = SmartRouter(config=cfg)

        with patch.object(router, "_get_reference_price", return_value=70000.0), patch.object(
            router,
            "_get_spread_bps",
            return_value=6.0,
        ):
            decision = router.decide("A005930", "buy", 2, market="auto")

        self.assertEqual(decision.market, "kr")

    def test_route_order_market_simulated(self) -> None:
        cfg = RouterConfig(
            small_notional_threshold_usd=100.0,
            medium_notional_threshold_usd=500.0,
            narrow_spread_bps=8.0,
            wide_spread_bps=25.0,
            track_slippage=False,
        )
        router = SmartRouter(config=cfg)

        with patch.object(router, "_get_reference_price", return_value=10.0), patch.object(
            router,
            "_get_spread_bps",
            return_value=3.0,
        ):
            out = router.route_order("AAPL", "buy", 5, market="us", simulate=True)

        self.assertTrue(out["ok"])
        self.assertEqual(out["decision"]["route"], "MARKET")
        self.assertEqual(out["execution"]["fill_count"], 1)


if __name__ == "__main__":
    unittest.main()
