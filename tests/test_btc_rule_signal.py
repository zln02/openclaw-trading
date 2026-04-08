"""v6.3: BTC 룰 기반 결정론적 신호 테스트 (LLM 의존 제거 검증).

매 케이스가 결정론적으로 같은 입력 → 같은 출력을 반환해야 한다.
BUY/SELL/HOLD 및 경계 조건, 극도공포, 거래량 면제 등 커버.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# 프로젝트 루트 PYTHONPATH 추가 (conftest와 동일)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 환경 스텁 (btc_trading_agent import 시 안전)
os.environ.setdefault("DRY_RUN", "1")
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "mock-key")
os.environ.setdefault("UPBIT_ACCESS_KEY", "test-key")
os.environ.setdefault("UPBIT_SECRET_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456")

from btc.btc_trading_agent import rule_based_btc_signal


def _base_inputs(**over):
    """기본 입력 (HOLD가 나오도록 평범한 값)."""
    base = dict(
        indicators={"price": 90_000_000, "rsi": 50, "macd": 0, "macd_histogram": 0},
        fg={"value": 50, "label": "중립", "msg": "중립"},
        htf={"trend": "SIDEWAYS", "rsi_1h": 50},
        volume={"ratio": 1.0, "label": "보통"},
        comp={"total": 40},
        rsi_d=50.0,
        momentum={"bb_pct": 50, "ret_7d": 0.0},
        funding={"rate": 0.01, "signal": "NEUTRAL"},
        ls_ratio={"ls_ratio": 1.0, "signal": "NEUTRAL"},
        regime="TRANSITION",
    )
    base.update(over)
    return base


class RuleBasedBtcSignalTests(unittest.TestCase):
    def test_determinism(self):
        """동일 입력 → 동일 출력 (2회 호출 비교)."""
        kw = _base_inputs()
        r1 = rule_based_btc_signal(**kw)
        r2 = rule_based_btc_signal(**kw)
        self.assertEqual(r1, r2)

    def test_source_field_present(self):
        """모든 신호에 source='RULE_BTC'가 포함되어야 함."""
        kw = _base_inputs()
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["source"], "RULE_BTC")
        self.assertIn("action", r)
        self.assertIn("confidence", r)

    def test_downtrend_overbought_sells(self):
        """DOWNTREND + 5m RSI 65+ → SELL."""
        kw = _base_inputs(
            htf={"trend": "DOWNTREND", "rsi_1h": 70},
            indicators={"price": 90_000_000, "rsi": 70, "macd": 0, "macd_histogram": 0},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "SELL")
        self.assertGreaterEqual(r["confidence"], 70)

    def test_extreme_greed_sells(self):
        """F&G >= 75 → SELL."""
        kw = _base_inputs(fg={"value": 80, "label": "극도탐욕", "msg": "탐욕"})
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "SELL")

    def test_overbought_daily_rsi_sells(self):
        """일봉 RSI>=70 + BB%>=80 → SELL."""
        kw = _base_inputs(
            rsi_d=72,
            momentum={"bb_pct": 85, "ret_7d": 5.0},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "SELL")

    def test_downtrend_blocks_buy(self):
        """DOWNTREND (과매수 아님) → HOLD (BUY 금지)."""
        kw = _base_inputs(
            htf={"trend": "DOWNTREND", "rsi_1h": 45},
            indicators={"price": 90_000_000, "rsi": 45, "macd": 0, "macd_histogram": 0},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "HOLD")

    def test_fg_above_55_blocks_buy(self):
        """F&G > 55 → HOLD (공포 구간 아님)."""
        kw = _base_inputs(fg={"value": 60, "label": "중립", "msg": "중립"})
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "HOLD")
        self.assertIn("F&G", r["reason"])

    def test_low_volume_blocks_buy(self):
        """거래량 0.3 이하 (비극도공포) → HOLD."""
        kw = _base_inputs(
            fg={"value": 40, "label": "공포", "msg": "공포"},
            volume={"ratio": 0.2, "label": "저조"},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "HOLD")
        self.assertIn("거래량", r["reason"])

    def test_extreme_fear_exempts_volume_filter(self):
        """F&G<=20 극도공포 + 거래량 0.2 (면제 0.15 초과) → BUY 후보."""
        # F&G=18 → 극도공포 면제, vol=0.2 > 0.15 통과
        # + 복합스코어 역발상 점수 + UPTREND
        kw = _base_inputs(
            fg={"value": 18, "label": "극도공포", "msg": "극도공포"},
            volume={"ratio": 0.2, "label": "저조"},
            htf={"trend": "UPTREND", "rsi_1h": 40},
            indicators={"price": 90_000_000, "rsi": 30, "macd": 10, "macd_histogram": 5},
            rsi_d=40.0,
            comp={"total": 65},
            momentum={"bb_pct": 30, "ret_7d": -2.0},
            funding={"rate": -0.01, "signal": "SHORT_CROWDED"},
            ls_ratio={"ls_ratio": 0.7, "signal": "SHORT_CROWDED"},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "BUY")
        self.assertGreaterEqual(r["confidence"], 65)

    def test_uptrend_fear_volume_surge_buys(self):
        """UPTREND + 공포 F&G + 거래량 급증 → BUY."""
        kw = _base_inputs(
            htf={"trend": "UPTREND", "rsi_1h": 45},
            fg={"value": 25, "label": "공포", "msg": "공포"},
            volume={"ratio": 2.5, "label": "급증"},
            indicators={"price": 90_000_000, "rsi": 40, "macd": 5, "macd_histogram": 2},
            rsi_d=45.0,
            comp={"total": 62},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "BUY")
        # 점수: UPTREND(20) + 극도공포25(25) + 거래량2x(15) + MACD양전(10) + dRSI양호(10) + 복합(10) = 90
        self.assertGreaterEqual(r["confidence"], 65)

    def test_insufficient_score_holds(self):
        """BUY 조건 일부 통과하나 점수 < 65 → HOLD."""
        kw = _base_inputs(
            fg={"value": 50, "label": "중립", "msg": "중립"},  # 공포 점수 0
            volume={"ratio": 1.0, "label": "보통"},              # 거래량 점수 0
            htf={"trend": "SIDEWAYS", "rsi_1h": 50},             # UPTREND 점수 0
            indicators={"price": 90_000_000, "rsi": 50, "macd": 0, "macd_histogram": 0},
            rsi_d=55.0,
            comp={"total": 30},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "HOLD")

    def test_buy_confidence_capped_at_95(self):
        """모든 BUY 점수 합산해도 신뢰도 상한 95."""
        kw = _base_inputs(
            htf={"trend": "UPTREND", "rsi_1h": 45},
            fg={"value": 10, "label": "극도공포", "msg": "극도공포"},
            volume={"ratio": 3.0, "label": "폭발"},
            indicators={"price": 90_000_000, "rsi": 25, "macd": 100, "macd_histogram": 50},
            rsi_d=40.0,
            comp={"total": 80},
            momentum={"bb_pct": 20, "ret_7d": 1.0},
            funding={"rate": -0.02, "signal": "SHORT_CROWDED"},
            ls_ratio={"ls_ratio": 0.5, "signal": "SHORT_CROWDED"},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "BUY")
        self.assertLessEqual(r["confidence"], 95)


if __name__ == "__main__":
    unittest.main()
