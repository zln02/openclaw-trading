"""Phase 12 agent smoke/unit tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from agents.news_analyst import NewsAnalyst
from agents.regime_classifier import RegimeClassifier
from agents.strategy_reviewer import StrategyReviewer
from common.cache import clear_cache


class StrategyReviewerTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_cache()
        self.tmp = tempfile.TemporaryDirectory()
        self.strategy_path = Path(self.tmp.name) / "today_strategy.json"
        self.reviewer = StrategyReviewer(supabase_client=None, strategy_path=self.strategy_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_is_review_day_only_sunday(self) -> None:
        d = date(2026, 1, 1)
        while d.weekday() != 6:  # Sunday
            d += timedelta(days=1)
        self.assertTrue(self.reviewer.is_review_day(d))
        self.assertFalse(self.reviewer.is_review_day(d + timedelta(days=1)))

    def test_fallback_review_adjusts_and_normalizes_factor_weights(self) -> None:
        current = {
            "top_picks": [],
            "factor_weights": {
                "momentum": 0.5,
                "quality": 0.2,
                "value": 0.1,
                "sentiment": 0.1,
                "technical": 0.1,
            },
        }
        weekly = {"overall_win_rate": 20.0, "overall_pnl_sum": -1000.0}
        out = self.reviewer._fallback_review(current, weekly)

        self.assertEqual(out.get("risk_level"), "높음")
        fw = out.get("factor_weights") or {}
        self.assertAlmostEqual(sum(fw.values()), 1.0, places=3)
        self.assertGreater(fw.get("quality", 0.0), fw.get("sentiment", 0.0))

    def test_merge_review_normalizes_factor_weights(self) -> None:
        base = {"factor_weights": {"momentum": 0.6, "value": 0.4}}
        review = {"factor_weights": {"momentum": 3.0, "value": 1.0}}
        out = self.reviewer._merge_review(base, review, date(2026, 2, 1))

        fw = out.get("factor_weights") or {}
        self.assertAlmostEqual(sum(fw.values()), 1.0, places=3)
        self.assertGreater(fw.get("momentum", 0.0), fw.get("value", 0.0))


class NewsAnalystTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_cache()

    def test_aggregate_sentiment(self) -> None:
        analyst = NewsAnalyst(daily_budget_usd=0.0)
        rows = [
            {"label": "POSITIVE", "strength": 5},
            {"label": "NEGATIVE", "strength": 5},
            {"label": "NEUTRAL", "strength": 3},
        ]
        agg = analyst.aggregate_sentiment(rows)

        self.assertEqual(agg["news_count"], 3)
        self.assertEqual(agg["positive"], 1)
        self.assertEqual(agg["negative"], 1)
        self.assertEqual(agg["neutral"], 1)
        self.assertAlmostEqual(agg["sentiment_score"], 0.0, places=6)

    def test_analyze_news_items_deduplicates_seen_ids(self) -> None:
        analyst = NewsAnalyst(daily_budget_usd=0.0)
        items = [
            {"id": "n1", "headline": "A", "symbols": ["BTC"], "timestamp": "2026-01-01T00:00:00Z"},
            {"id": "n1", "headline": "A-dup", "symbols": ["BTC"], "timestamp": "2026-01-01T00:01:00Z"},
            {"id": "n2", "headline": "B", "symbols": ["ETH"], "timestamp": "2026-01-01T00:02:00Z"},
        ]

        with patch.object(
            NewsAnalyst,
            "analyze_item",
            return_value={
                "label": "NEUTRAL",
                "strength": 2,
                "reason": "",
                "confidence": 0.5,
                "model": "RULE",
            },
        ):
            first = analyst.analyze_news_items(items, default_symbol="BTC")
            second = analyst.analyze_news_items(items, default_symbol="BTC")

        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 0)


class RegimeClassifierTests(unittest.TestCase):
    def test_classify_rule_crisis(self) -> None:
        clf = RegimeClassifier()
        feat = {
            "vix_level": 40.0,
            "spy_ret_20d": -0.2,
            "spy_vol_20d": 0.05,
            "credit_spread_proxy": -0.05,
            "corr_shift_20_60": 0.2,
        }
        out = clf.classify_rule(feat)
        self.assertEqual(out.regime, "CRISIS")
        self.assertEqual(out.preset.get("max_positions"), 1)

    def test_get_preset_case_insensitive(self) -> None:
        clf = RegimeClassifier()
        preset = clf.get_preset("risk_on")
        self.assertEqual(preset.get("max_positions"), 7)


if __name__ == "__main__":
    unittest.main()
