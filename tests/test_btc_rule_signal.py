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


    # ── P0: 필수 3개 ──────────────────────────────────────────────────────────

    def test_sell_precedence_over_buy_gate(self):
        """DOWNTREND + 5m RSI 70 → SELL 조건이 BUY 필수 검사보다 먼저 실행됨."""
        # SELL 조건 1: trend=="DOWNTREND" and rsi_5m >= 65
        # BUY 필수 조건 1도 DOWNTREND 차단이지만, SELL이 먼저 평가됨
        # → action이 SELL이어야 하고, confidence 75
        kw = _base_inputs(
            htf={"trend": "DOWNTREND", "rsi_1h": 70},
            indicators={"price": 90_000_000, "rsi": 70, "macd": 0, "macd_histogram": 0},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "SELL")
        self.assertEqual(r["confidence"], 75)
        self.assertEqual(r["source"], "RULE_BTC")

    def test_sideways_trend_buys_without_uptrend_bonus(self):
        """SIDEWAYS 추세에서도 다른 점수 합산으로 BUY 가능 (UPTREND +20 없이)."""
        # SIDEWAYS: +0 (UPTREND 아님)
        # F&G=15 (<=25): +25
        # vol_ratio=2.5 (>=2.0): +15
        # macd=5, macd_hist=2 (둘 다 양수): +10
        # rsi_5m=30 (<35): +10
        # rsi_d=40, ret_7d=0 (rsi_d<50 and ret_7d>-5): +10
        # 합계: 0+25+15+10+10+10 = 70 → BUY
        kw = _base_inputs(
            htf={"trend": "SIDEWAYS", "rsi_1h": 50},
            fg={"value": 15, "label": "극도공포", "msg": "극도공포"},
            volume={"ratio": 2.5, "label": "급증"},
            indicators={"price": 90_000_000, "rsi": 30, "macd": 5, "macd_histogram": 2},
            rsi_d=40.0,
            momentum={"bb_pct": 30, "ret_7d": 0.0},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "BUY")
        self.assertGreaterEqual(r["confidence"], 65)
        self.assertEqual(r["source"], "RULE_BTC")

    def test_none_optional_dicts_no_crash(self):
        """momentum=None, funding=None, ls_ratio=None, comp=None 전달 시 예외 없이 dict 반환."""
        r = rule_based_btc_signal(
            indicators={"price": 90_000_000, "rsi": 50, "macd": 0, "macd_histogram": 0},
            fg={"value": 50, "label": "중립", "msg": "중립"},
            htf={"trend": "SIDEWAYS", "rsi_1h": 50},
            volume={"ratio": 1.0, "label": "보통"},
            momentum=None,
            funding=None,
            ls_ratio=None,
            comp=None,
        )
        self.assertIsInstance(r, dict)
        self.assertIn("action", r)
        self.assertIn("confidence", r)
        self.assertIn("reason", r)
        self.assertIn("source", r)
        self.assertEqual(r["source"], "RULE_BTC")

    # ── P1: 경계 8개 ──────────────────────────────────────────────────────────

    def test_fg_boundary_55_buy_candidate(self):
        """F&G=55 → BUY 필수(fg_val>55) 통과. 충분한 점수면 BUY."""
        # F&G=55는 > 55 조건 불만족 → 필수 통과
        # 점수: UPTREND(+20) + F&G<=25? No, 55>40 → 0 + vol>=2.0(+15) + MACD(+10) + rsi_5m<35(+10) + dRSI(+10) = 65 → BUY
        kw = _base_inputs(
            fg={"value": 55, "label": "탐욕", "msg": "탐욕"},
            htf={"trend": "UPTREND", "rsi_1h": 45},
            volume={"ratio": 2.0, "label": "급증"},
            indicators={"price": 90_000_000, "rsi": 30, "macd": 5, "macd_histogram": 2},
            rsi_d=45.0,
            momentum={"bb_pct": 40, "ret_7d": 0.0},
        )
        r = rule_based_btc_signal(**kw)
        # F&G 차단("F&G") 없이 BUY가 나와야 함
        self.assertEqual(r["action"], "BUY")
        self.assertNotIn("F&G", r["reason"])

    def test_fg_boundary_56_blocks_buy(self):
        """F&G=56 → HOLD + reason에 'F&G' 포함."""
        kw = _base_inputs(
            fg={"value": 56, "label": "탐욕", "msg": "탐욕"},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "HOLD")
        self.assertIn("F&G", r["reason"])

    def test_fg_boundary_20_extreme_fear_volume_exempt(self):
        """F&G=20(극도공포) + vol_ratio=0.2 → 면제 임계(0.15) 초과로 거래량 통과."""
        # F&G=20 → is_extreme_fear=True, min_vol=0.15
        # vol_ratio=0.2 > 0.15 → 거래량 필수 통과
        # 점수: UPTREND(+20) + F&G<=25(+25) = 45, 나머지 없으면 HOLD지만 거래량 차단은 안 됨
        # 거래량 차단 안 된다는 것만 검증 (reason에 "거래량" 없음)
        kw = _base_inputs(
            fg={"value": 20, "label": "극도공포", "msg": "극도공포"},
            volume={"ratio": 0.2, "label": "저조"},
            htf={"trend": "UPTREND", "rsi_1h": 45},
        )
        r = rule_based_btc_signal(**kw)
        # 거래량 때문에 HOLD가 아니어야 함
        self.assertNotIn("거래량", r["reason"])
        self.assertEqual(r["source"], "RULE_BTC")

    def test_fg_boundary_21_not_extreme_fear(self):
        """F&G=21(극도공포 아님) + vol_ratio=0.2 → min_vol=0.3 적용, 거래량 차단 → HOLD."""
        # F&G=21 → is_extreme_fear=False (<=20 불만족), min_vol=0.3
        # vol_ratio=0.2 <= 0.3 → 거래량 필수 HOLD
        kw = _base_inputs(
            fg={"value": 21, "label": "극도공포", "msg": "극도공포"},
            volume={"ratio": 0.2, "label": "저조"},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "HOLD")
        self.assertIn("거래량", r["reason"])

    def test_volume_boundary_exact_0_3_blocks(self):
        """vol_ratio=0.3(비극도공포) → <= 0.3 조건 만족, 거래량 차단 HOLD."""
        kw = _base_inputs(
            fg={"value": 40, "label": "공포", "msg": "공포"},
            volume={"ratio": 0.3, "label": "저조"},
        )
        r = rule_based_btc_signal(**kw)
        self.assertEqual(r["action"], "HOLD")
        self.assertIn("거래량", r["reason"])

    def test_volume_boundary_0_31_passes(self):
        """vol_ratio=0.31(비극도공포) → 0.3 초과, 거래량 필수 통과."""
        # 거래량 통과 후 점수 미달이면 HOLD이지만 reason에 "거래량" 없어야 함
        kw = _base_inputs(
            fg={"value": 40, "label": "공포", "msg": "공포"},
            volume={"ratio": 0.31, "label": "저조"},
            htf={"trend": "SIDEWAYS", "rsi_1h": 50},
        )
        r = rule_based_btc_signal(**kw)
        # 거래량으로 인한 차단이 아닌 다른 이유
        self.assertNotIn("거래량", r["reason"])
        self.assertEqual(r["source"], "RULE_BTC")

    def test_fear_range_25_to_40_gets_15_bonus(self):
        """F&G=35(공포) → +15 보너스. F&G=25 → +25 보너스. confidence 차이 10 이상."""
        # F&G=35: +15, F&G=25: +25 (나머지 동일)
        # UPTREND(+20), vol 2.5(+15), MACD(+10), rsi_5m 30(+10), dRSI(+10)
        base_kw = dict(
            htf={"trend": "UPTREND", "rsi_1h": 45},
            volume={"ratio": 2.5, "label": "급증"},
            indicators={"price": 90_000_000, "rsi": 30, "macd": 5, "macd_histogram": 2},
            rsi_d=45.0,
            momentum={"bb_pct": 30, "ret_7d": 0.0},
        )
        r_35 = rule_based_btc_signal(**_base_inputs(fg={"value": 35, "label": "공포", "msg": "공포"}, **base_kw))
        r_25 = rule_based_btc_signal(**_base_inputs(fg={"value": 25, "label": "공포", "msg": "공포"}, **base_kw))
        # 둘 다 BUY여야 함
        self.assertEqual(r_35["action"], "BUY")
        self.assertEqual(r_25["action"], "BUY")
        # F&G=25쪽이 10점 더 높아야 함 (25 vs 15 보너스 차이)
        self.assertEqual(r_25["confidence"] - r_35["confidence"], 10)

    def test_macd_requires_both_positive_for_bonus(self):
        """macd>0, macd_hist=0 → MACD 보너스 0. macd>0, macd_hist>0 → +10."""
        # 두 케이스 모두 나머지 조건 동일하게 설정하여 confidence 차이 10 확인
        # 점수가 MACD 보너스 없이 BUY 임계(65) 이상인 기본값 사용
        base_kw = _base_inputs(
            htf={"trend": "UPTREND", "rsi_1h": 45},
            fg={"value": 25, "label": "공포", "msg": "공포"},
            volume={"ratio": 2.5, "label": "급증"},
            rsi_d=45.0,
            momentum={"bb_pct": 30, "ret_7d": 0.0},
        )
        # macd>0 but macd_hist=0 → MACD 보너스 없음
        kw_no_macd = dict(base_kw)
        kw_no_macd["indicators"] = {"price": 90_000_000, "rsi": 40, "macd": 5, "macd_histogram": 0}
        # macd>0 and macd_hist>0 → MACD 보너스 +10
        kw_with_macd = dict(base_kw)
        kw_with_macd["indicators"] = {"price": 90_000_000, "rsi": 40, "macd": 5, "macd_histogram": 2}

        r_no = rule_based_btc_signal(**kw_no_macd)
        r_yes = rule_based_btc_signal(**kw_with_macd)
        # MACD 보너스 케이스가 10점 더 높아야 함
        self.assertEqual(r_yes["confidence"] - r_no["confidence"], 10)

    # ── P2: 단독 보너스 4개 ────────────────────────────────────────────────────

    def test_funding_negative_bonus_adds_5(self):
        """음수 펀딩비(rate<0) → +5점. 양수 펀딩비보다 confidence 5 높아야 함."""
        # 기준: UPTREND(+20) + F&G=25(+25) + vol 2.5(+15) = 60, 나머지 0
        # rate=0.01: 0점 → 총 60점 → HOLD (60<65)
        # rate=-0.01: +5 → 총 65점 → BUY
        base_kw = _base_inputs(
            htf={"trend": "UPTREND", "rsi_1h": 45},
            fg={"value": 25, "label": "공포", "msg": "공포"},
            volume={"ratio": 2.5, "label": "급증"},
            indicators={"price": 90_000_000, "rsi": 45, "macd": 0, "macd_histogram": 0},
            rsi_d=55.0,
            momentum={"bb_pct": 30, "ret_7d": 0.0},
            ls_ratio={"ls_ratio": 1.0, "signal": "NEUTRAL"},
            comp={"total": 30},
        )
        kw_pos = dict(base_kw)
        kw_pos["funding"] = {"rate": 0.01, "signal": "NEUTRAL"}
        kw_neg = dict(base_kw)
        kw_neg["funding"] = {"rate": -0.01, "signal": "SHORT_CROWDED"}

        r_pos = rule_based_btc_signal(**kw_pos)
        r_neg = rule_based_btc_signal(**kw_neg)
        # 음수 펀딩이 5점 더 높아야 함
        self.assertEqual(r_neg["confidence"] - r_pos["confidence"], 5)

    def test_ls_ratio_short_crowded_bonus_adds_5(self):
        """ls_ratio<0.8 → +5점. ls_ratio=1.0보다 confidence 5 높아야 함."""
        # 기준: UPTREND(+20) + F&G=25(+25) + vol 2.5(+15) + fund 음수(+5) = 65 → BUY
        # ls_ratio=1.0: +0 → confidence=65
        # ls_ratio=0.7: +5 → confidence=70
        base_kw = _base_inputs(
            htf={"trend": "UPTREND", "rsi_1h": 45},
            fg={"value": 25, "label": "공포", "msg": "공포"},
            volume={"ratio": 2.5, "label": "급증"},
            indicators={"price": 90_000_000, "rsi": 45, "macd": 0, "macd_histogram": 0},
            rsi_d=55.0,
            momentum={"bb_pct": 30, "ret_7d": 0.0},
            funding={"rate": -0.01, "signal": "SHORT_CROWDED"},
            comp={"total": 30},
        )
        kw_neutral = dict(base_kw)
        kw_neutral["ls_ratio"] = {"ls_ratio": 1.0, "signal": "NEUTRAL"}
        kw_short = dict(base_kw)
        kw_short["ls_ratio"] = {"ls_ratio": 0.7, "signal": "SHORT_CROWDED"}

        r_neutral = rule_based_btc_signal(**kw_neutral)
        r_short = rule_based_btc_signal(**kw_short)
        self.assertEqual(r_short["confidence"] - r_neutral["confidence"], 5)

    def test_all_branches_return_source_rule_btc(self):
        """SELL 3분기, HOLD 3분기, BUY 1분기 — 모두 source='RULE_BTC'."""
        cases = [
            # SELL 분기 1: DOWNTREND + rsi_5m>=65
            _base_inputs(
                htf={"trend": "DOWNTREND", "rsi_1h": 70},
                indicators={"price": 90_000_000, "rsi": 65, "macd": 0, "macd_histogram": 0},
            ),
            # SELL 분기 2: F&G>=75
            _base_inputs(fg={"value": 75, "label": "극도탐욕", "msg": "탐욕"}),
            # SELL 분기 3: rsi_d>=70 + bb_pct>=80
            _base_inputs(rsi_d=70.0, momentum={"bb_pct": 80, "ret_7d": 0.0}),
            # HOLD 분기 1: DOWNTREND (SELL 조건 미달)
            _base_inputs(
                htf={"trend": "DOWNTREND", "rsi_1h": 45},
                indicators={"price": 90_000_000, "rsi": 45, "macd": 0, "macd_histogram": 0},
            ),
            # HOLD 분기 2: F&G>55
            _base_inputs(fg={"value": 60, "label": "탐욕", "msg": "탐욕"}),
            # HOLD 분기 3: 거래량 부족 (비극도공포)
            _base_inputs(
                fg={"value": 40, "label": "공포", "msg": "공포"},
                volume={"ratio": 0.3, "label": "저조"},
            ),
            # BUY 분기
            _base_inputs(
                htf={"trend": "UPTREND", "rsi_1h": 45},
                fg={"value": 20, "label": "극도공포", "msg": "극도공포"},
                volume={"ratio": 2.5, "label": "급증"},
                indicators={"price": 90_000_000, "rsi": 30, "macd": 5, "macd_histogram": 2},
                rsi_d=40.0,
                comp={"total": 65},
                momentum={"bb_pct": 30, "ret_7d": 0.0},
                funding={"rate": -0.01, "signal": "SHORT_CROWDED"},
                ls_ratio={"ls_ratio": 0.7, "signal": "SHORT_CROWDED"},
            ),
        ]
        for i, kw in enumerate(cases):
            with self.subTest(case=i):
                r = rule_based_btc_signal(**kw)
                self.assertEqual(r["source"], "RULE_BTC", f"case {i}: source 불일치")


if __name__ == "__main__":
    unittest.main()
