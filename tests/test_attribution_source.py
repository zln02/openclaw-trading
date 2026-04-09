"""v6.3: WeeklyAttributionRunner._calc_source_attribution 단위 테스트.

signal_source별 PnL 집계 로직의 경계 조건을 모두 커버한다.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# 프로젝트 루트 PYTHONPATH 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 환경 스텁 — Supabase/Anthropic import 시 안전하게
os.environ.setdefault("DRY_RUN", "1")
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "mock-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456")

from quant.portfolio.attribution import WeeklyAttributionRunner


def _make_runner() -> WeeklyAttributionRunner:
    """생성자를 그대로 호출한다.
    __init__이 try/except로 Supabase 접근 실패를 흡수하므로
    mock 환경에서도 self.supabase = None 으로 안전하게 생성된다.
    """
    return WeeklyAttributionRunner()


class TestCalcSourceAttribution(unittest.TestCase):
    """_calc_source_attribution 7가지 케이스."""

    def setUp(self):
        self.runner = _make_runner()

    # ── 케이스 1 ──────────────────────────────────────────────────────────
    def test_empty_trades_returns_empty_dict(self):
        """빈 리스트 입력 시 빈 dict 반환."""
        result = self.runner._calc_source_attribution([])
        self.assertEqual(result, {})

    # ── 케이스 2 ──────────────────────────────────────────────────────────
    def test_single_source_aggregation(self):
        """같은 source 3건 → trades/total/avg/win_rate 4자리 반올림 검증."""
        trades = [
            {"signal_source": "RULE_BTC", "pnl_pct": 2.0},
            {"signal_source": "RULE_BTC", "pnl_pct": -1.0},
            {"signal_source": "RULE_BTC", "pnl_pct": 3.0},
        ]
        result = self.runner._calc_source_attribution(trades)

        self.assertIn("RULE_BTC", result)
        bucket = result["RULE_BTC"]
        self.assertEqual(bucket["trades"], 3)
        self.assertAlmostEqual(bucket["total_pnl_pct"], 4.0, places=4)
        # avg = 4.0/3 = 1.333... → round(4) = 1.3333
        self.assertAlmostEqual(bucket["avg_pnl_pct"], 1.3333, places=4)
        # win: [2.0, 3.0] = 2건 → 2/3 = 0.6667
        self.assertAlmostEqual(bucket["win_rate"], 0.6667, places=4)

    # ── 케이스 3 ──────────────────────────────────────────────────────────
    def test_multi_source_separation(self):
        """RULE_BTC 2건 + RULE_COMPOSITE 3건 → 키 2개, 각 trades 수 정확."""
        trades = [
            {"signal_source": "RULE_BTC", "pnl_pct": 1.0},
            {"signal_source": "RULE_BTC", "pnl_pct": -0.5},
            {"signal_source": "RULE_COMPOSITE", "pnl_pct": 0.3},
            {"signal_source": "RULE_COMPOSITE", "pnl_pct": 0.5},
            {"signal_source": "RULE_COMPOSITE", "pnl_pct": -0.2},
        ]
        result = self.runner._calc_source_attribution(trades)

        self.assertEqual(len(result), 2)
        self.assertEqual(result["RULE_BTC"]["trades"], 2)
        self.assertEqual(result["RULE_COMPOSITE"]["trades"], 3)

    # ── 케이스 4 ──────────────────────────────────────────────────────────
    def test_unknown_fallback_when_source_missing(self):
        """signal_source 키 누락 또는 None → 'UNKNOWN' 버킷 집계."""
        # 키 자체가 없는 경우
        trade_no_key = {"pnl_pct": 1.5}
        # 명시적 None인 경우
        trade_none = {"signal_source": None, "pnl_pct": 2.0}

        result = self.runner._calc_source_attribution([trade_no_key, trade_none])

        self.assertIn("UNKNOWN", result)
        self.assertEqual(result["UNKNOWN"]["trades"], 2)
        # 다른 버킷 없어야 함
        self.assertEqual(len(result), 1)

    # ── 케이스 5 ──────────────────────────────────────────────────────────
    def test_win_rate_calculation(self):
        """2승 2패 → win_rate=0.5, total=3.0, avg=0.75."""
        trades = [
            {"signal_source": "TEST", "pnl_pct": 5.0},
            {"signal_source": "TEST", "pnl_pct": 2.0},
            {"signal_source": "TEST", "pnl_pct": -3.0},
            {"signal_source": "TEST", "pnl_pct": -1.0},
        ]
        result = self.runner._calc_source_attribution(trades)
        bucket = result["TEST"]

        self.assertAlmostEqual(bucket["win_rate"], 0.5, places=4)
        self.assertAlmostEqual(bucket["total_pnl_pct"], 3.0, places=4)
        self.assertAlmostEqual(bucket["avg_pnl_pct"], 0.75, places=4)

    # ── 케이스 6 ──────────────────────────────────────────────────────────
    def test_all_losses_zero_win_rate(self):
        """전패 → win_rate=0.0, total=-3.5."""
        trades = [
            {"signal_source": "RULE_KR", "pnl_pct": -1.0},
            {"signal_source": "RULE_KR", "pnl_pct": -2.0},
            {"signal_source": "RULE_KR", "pnl_pct": -0.5},
        ]
        result = self.runner._calc_source_attribution(trades)
        bucket = result["RULE_KR"]

        self.assertEqual(bucket["win_rate"], 0.0)
        self.assertAlmostEqual(bucket["total_pnl_pct"], -3.5, places=4)

    # ── 케이스 7 ──────────────────────────────────────────────────────────
    def test_pnl_rounding_4_decimals(self):
        """소수점 긴 값 → total/avg 모두 round(x, 4) 적용 확인."""
        pnl_a = 0.123456789
        pnl_b = 0.987654321
        trades = [
            {"signal_source": "FRAC", "pnl_pct": pnl_a},
            {"signal_source": "FRAC", "pnl_pct": pnl_b},
        ]
        result = self.runner._calc_source_attribution(trades)
        bucket = result["FRAC"]

        expected_total = round(pnl_a + pnl_b, 4)  # 1.1111
        expected_avg = round((pnl_a + pnl_b) / 2, 4)  # 0.5556

        self.assertEqual(bucket["total_pnl_pct"], expected_total)
        self.assertEqual(bucket["avg_pnl_pct"], expected_avg)


if __name__ == "__main__":
    unittest.main()
