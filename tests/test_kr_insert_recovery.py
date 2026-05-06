"""KR trade_executions 끊김 복구 회귀 테스트.

두 silent 버그 (source 컬럼 + DrawdownGuardState.triggered_rules) fix 검증.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from quant.risk.drawdown_guard import DrawdownGuard, DrawdownGuardState

# ────────────────────────────────────────────────────────────────────────────
# D fix — stock_trading_agent.py 'source' INSERT 키 제거 검증
# ────────────────────────────────────────────────────────────────────────────

def test_no_source_key_in_trade_executions_insert():
    """4-19 마이그레이션으로 trade_executions.source → signal_source 변경됨.
    INSERT 페이로드에 'source' 키 잔존 시 PGRST204 silent fail 유발.
    """
    src_path = Path(__file__).resolve().parent.parent / "stocks" / "stock_trading_agent.py"
    src = src_path.read_text(encoding="utf-8")
    # INSERT 페이로드 패턴만 매칭 (텔레그램 메시지/strategy 빌더 등은 제외)
    matches = re.findall(r"^\s*'source':\s*signal\.get\('source'", src, re.MULTILINE)
    assert matches == [], (
        f"stock_trading_agent.py 에 'source' INSERT 키가 {len(matches)}곳 잔존. "
        "4-19 마이그레이션 후 trade_executions 에 source 컬럼 없음 (PGRST204)."
    )


# ────────────────────────────────────────────────────────────────────────────
# E fix — DrawdownGuardState.triggered_rules 필드 검증
# ────────────────────────────────────────────────────────────────────────────

class TestDrawdownGuardStateTriggeredRules:
    def test_state_default_empty_triggered_rules(self):
        state = DrawdownGuardState()
        assert state.triggered_rules == []

    def test_state_accepts_triggered_rules(self):
        state = DrawdownGuardState(triggered_rules=["DAILY_BUY_BLOCK"])
        assert state.triggered_rules == ["DAILY_BUY_BLOCK"]

    def test_state_unpack_from_drawdown_state_json_kr_shape(self):
        """brain/risk/drawdown_state.json 의 kr 영역 형태 그대로 unpack 호환.

        호스트 cron 장중 abort 의 직접 원인: dataclass 에 triggered_rules 필드 없어서
        DrawdownGuardState(**load_drawdown_state('kr')) 가 TypeError.
        """
        payload = {
            "cooldown_until": None,
            "last_action": "NONE",
            "triggered_rules": [],
        }
        # 이 호출이 TypeError 안 나야 함 — 회귀 테스트의 핵심
        state = DrawdownGuardState(**payload)
        assert state.cooldown_until is None
        assert state.last_action == "NONE"
        assert state.triggered_rules == []

    def test_state_unpack_legacy_payload_no_triggered_rules(self):
        """옛 JSON (triggered_rules 키 없음) 도 호환 — default_factory=list 로 빈 list."""
        payload = {"cooldown_until": "2026-05-10", "last_action": "DAILY_BUY_BLOCK"}
        state = DrawdownGuardState(**payload)
        assert state.cooldown_until == "2026-05-10"
        assert state.last_action == "DAILY_BUY_BLOCK"
        assert state.triggered_rules == []

    def test_state_round_trip_with_asdict(self):
        original = DrawdownGuardState(
            cooldown_until="2026-05-10",
            last_action="WEEKLY_DELEVERAGE",
            triggered_rules=["WEEKLY_DELEVERAGE"],
        )
        serialized = asdict(original)
        restored = DrawdownGuardState(**serialized)
        assert restored == original

    def test_evaluate_works_after_unpack_with_triggered_rules(self):
        """state 가 triggered_rules 필드 가진 채로 evaluate() 호출돼도 정상 동작."""
        guard = DrawdownGuard()
        state = DrawdownGuardState(triggered_rules=["LEGACY"])
        decision = guard.evaluate(
            daily_return=-0.012,
            weekly_return=-0.033,
            monthly_return=-0.05,
            state=state,
        )
        # daily 만 트리거 (-1.2% < -2% 한도 미달, 단 daily 한도 -2% 와 -1.2% 비교 시 통과)
        assert isinstance(decision.get("triggered_rules"), list)
        assert "next_state" not in decision  # state 는 별 키 'state' 로
        assert "state" in decision
