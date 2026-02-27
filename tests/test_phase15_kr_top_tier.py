"""Phase 15 KR top-tier module tests."""
from __future__ import annotations

import unittest

from stocks.signals.dart_realtime import classify_disclosure
from stocks.signals.flow_kr import classify_investor_flow
from stocks.signals.orderbook_kr import analyze_orderbook_snapshot
from stocks.strategies.sector_rotation import SectorRotationModel, rank_sector_strength


class KROrderbookTests(unittest.TestCase):
    def test_orderbook_bullish_with_bid_wall(self) -> None:
        snapshot = {
            "symbol": "005930",
            "bids": [
                {"price": 70000, "qty": 3000},
                {"price": 69900, "qty": 1200},
                {"price": 69800, "qty": 1100},
            ],
            "asks": [
                {"price": 70100, "qty": 800},
                {"price": 70200, "qty": 750},
                {"price": 70300, "qty": 700},
            ],
        }
        out = analyze_orderbook_snapshot(snapshot, wall_multiplier=2.0)
        self.assertEqual(out["direction"], "BULLISH")
        self.assertGreater(out["wall_bid_count"], 0)


class KRFlowTests(unittest.TestCase):
    def test_flow_strong_buy_signal(self) -> None:
        rows = [
            {"date": "2026-02-20", "foreign_net": 1200, "institution_net": 800, "retail_net": -2000},
            {"date": "2026-02-21", "foreign_net": 900, "institution_net": 300, "retail_net": -1200},
            {"date": "2026-02-22", "foreign_net": 700, "institution_net": 200, "retail_net": -900},
            {"date": "2026-02-23", "foreign_net": 400, "institution_net": 100, "retail_net": -500},
            {"date": "2026-02-24", "foreign_net": 500, "institution_net": 150, "retail_net": -650},
        ]
        out = classify_investor_flow(rows)
        self.assertEqual(out["signal"], "STRONG_BUY")
        self.assertGreaterEqual(out["foreign_streak_days"], 5)
        self.assertGreater(out["score"], 70)


class DartRealtimeTests(unittest.TestCase):
    def test_buyback_disclosure_classification(self) -> None:
        out = classify_disclosure("자기주식 취득결정")
        self.assertEqual(out["category"], "BUYBACK")
        self.assertEqual(out["signal"], "BUY_STRONG")

    def test_rights_issue_disclosure_classification(self) -> None:
        out = classify_disclosure("유상증자 결정")
        self.assertEqual(out["category"], "RIGHTS_ISSUE")
        self.assertEqual(out["signal"], "SELL_STRONG")


class SectorRotationTests(unittest.TestCase):
    def test_rank_sector_strength(self) -> None:
        ranked = rank_sector_strength(
            {
                "TECHNOLOGY": 12.0,
                "ENERGY": 4.0,
                "UTILITIES": -3.0,
                "FINANCIALS": 7.0,
                "HEALTH_CARE": -1.0,
            },
            top_n=2,
            bottom_n=2,
        )
        self.assertEqual(ranked["top"][0]["sector"], "TECHNOLOGY")
        self.assertEqual(len(ranked["bottom"]), 2)

    def test_monthly_rebalance_due(self) -> None:
        model = SectorRotationModel()
        out = model.build_monthly_rotation(
            prices_by_sector={
                "TECHNOLOGY": [100, 105, 110],
                "ENERGY": [100, 98, 95],
                "FINANCIALS": [100, 103, 106],
                "UTILITIES": [100, 100, 99],
            },
            last_rebalance_date="2026-01-15",
            as_of="2026-02-27",
            top_n=2,
            bottom_n=2,
        )
        self.assertTrue(out["rebalance_due"])
        self.assertEqual(len(out["top_sectors"]), 2)
        self.assertEqual(len(out["avoid_sectors"]), 2)


if __name__ == "__main__":
    unittest.main()
