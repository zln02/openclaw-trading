"""DrawdownGuard 단위 테스트 — 5개 이상 시나리오 검증."""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from quant.risk.drawdown_guard import (DrawdownGuard, DrawdownGuardConfig,
                                       DrawdownGuardState)


@pytest.fixture
def guard():
    """기본 설정 DrawdownGuard (store 없이)."""
    return DrawdownGuard(config=DrawdownGuardConfig())


@pytest.fixture
def clean_state():
    return DrawdownGuardState()


# ── 테스트 1: 일일 손실 -2% 초과 시 신규 매수 차단 ──────────────────────────────
class TestDailyLossBlock:
    def test_daily_loss_exceeds_limit_blocks_buys(self, guard, clean_state):
        """daily_return -2.1% → DAILY_BUY_BLOCK, allow_new_buys=False."""
        result = guard.evaluate(
            daily_return=-0.021,
            weekly_return=-0.01,
            monthly_return=-0.01,
            state=clean_state,
        )
        assert result["allow_new_buys"] is False
        assert "DAILY_BUY_BLOCK" in result["triggered_rules"]

    def test_daily_loss_exactly_at_limit_does_not_block(self, guard, clean_state):
        """daily_return -1.99% → 한도 미달, 차단 없음."""
        result = guard.evaluate(
            daily_return=-0.0199,
            weekly_return=0.0,
            monthly_return=0.0,
            state=clean_state,
        )
        # intraday limit은 -1.5% 이하, daily limit은 -2.0% 이하
        # -1.99%는 intraday(-1.5%) 이하이므로 INTRADAY_LOSS_BLOCK 발생
        assert "DAILY_BUY_BLOCK" not in result["triggered_rules"]
        assert "MONTHLY_STOP" not in result["triggered_rules"]
        assert "WEEKLY_DELEVERAGE" not in result["triggered_rules"]

    def test_no_loss_allows_buys(self, guard, clean_state):
        """손실 없음 → 모든 플래그 정상."""
        result = guard.evaluate(
            daily_return=0.005,
            weekly_return=0.01,
            monthly_return=0.02,
            state=clean_state,
        )
        assert result["allow_new_buys"] is True
        assert result["force_liquidate"] is False
        assert result["reduce_positions_ratio"] == 0.0
        assert result["triggered_rules"] == []


# ── 테스트 2: 주간 손실 -5% 초과 시 WEEKLY_DELEVERAGE + reduce_positions_ratio ──
class TestWeeklyDeleverage:
    def test_weekly_loss_triggers_deleverage(self, guard, clean_state):
        """weekly_return -5.1% → WEEKLY_DELEVERAGE, reduce 50%."""
        result = guard.evaluate(
            daily_return=-0.01,
            weekly_return=-0.051,
            monthly_return=-0.04,
            state=clean_state,
        )
        assert result["allow_new_buys"] is False
        assert "WEEKLY_DELEVERAGE" in result["triggered_rules"]
        assert result["reduce_positions_ratio"] == 0.50

    def test_weekly_deleverage_no_cooldown_set(self, guard, clean_state):
        """WEEKLY_DELEVERAGE는 cooldown을 새로 설정하지 않는다."""
        result = guard.evaluate(
            daily_return=-0.01,
            weekly_return=-0.06,
            monthly_return=-0.04,
            state=clean_state,
        )
        assert "WEEKLY_DELEVERAGE" in result["triggered_rules"]
        assert "MONTHLY_STOP" not in result["triggered_rules"]
        # cooldown_until은 이전 state에서 유지(None)
        assert result["cooldown_until"] is None

    def test_state_records_weekly_deleverage_action(self, guard, clean_state):
        """next_state가 last_action='WEEKLY_DELEVERAGE'를 기록한다."""
        result = guard.evaluate(
            daily_return=-0.01,
            weekly_return=-0.055,
            monthly_return=-0.04,
            state=clean_state,
        )
        assert result["state"].last_action == "WEEKLY_DELEVERAGE"


# ── 테스트 3: 월간 손실 -10% 초과 시 전면 중지 + cooldown 설정 ──────────────────
class TestMonthlyStop:
    def test_monthly_loss_force_liquidate(self, guard, clean_state):
        """monthly_return -10.1% → force_liquidate=True, reduce=100%."""
        result = guard.evaluate(
            daily_return=-0.03,
            weekly_return=-0.06,
            monthly_return=-0.101,
            state=clean_state,
        )
        assert result["force_liquidate"] is True
        assert result["reduce_positions_ratio"] == 1.0
        assert result["allow_new_buys"] is False
        assert "MONTHLY_STOP" in result["triggered_rules"]

    def test_monthly_stop_sets_cooldown_7days(self, guard, clean_state):
        """MONTHLY_STOP은 7일 cooldown을 설정한다."""
        today = date(2026, 4, 21)
        result = guard.evaluate(
            daily_return=-0.05,
            weekly_return=-0.10,
            monthly_return=-0.12,
            as_of=today,
            state=clean_state,
        )
        expected_cooldown = (today + timedelta(days=7)).isoformat()
        assert result["cooldown_until"] == expected_cooldown

    def test_monthly_overrides_weekly(self, guard, clean_state):
        """월간·주간 동시 초과 시 MONTHLY_STOP이 WEEKLY_DELEVERAGE를 대체한다."""
        result = guard.evaluate(
            daily_return=-0.03,
            weekly_return=-0.08,
            monthly_return=-0.15,
            state=clean_state,
        )
        assert "MONTHLY_STOP" in result["triggered_rules"]
        assert "WEEKLY_DELEVERAGE" not in result["triggered_rules"]


# ── 테스트 4: intraday -1.5% 임계 ────────────────────────────────────────────
class TestIntradayLimit:
    def test_intraday_loss_blocks_buys(self, guard, clean_state):
        """-1.5% 이하 일중 손실 → INTRADAY_LOSS_BLOCK."""
        result = guard.evaluate(
            daily_return=-0.015,
            weekly_return=-0.01,
            monthly_return=-0.01,
            state=clean_state,
        )
        assert "INTRADAY_LOSS_BLOCK" in result["triggered_rules"]
        assert result["allow_new_buys"] is False

    def test_intraday_below_daily_still_triggers(self, guard, clean_state):
        """-1.6%: intraday limit 초과지만 daily limit(-2%) 미달 → INTRADAY만 발동."""
        result = guard.evaluate(
            daily_return=-0.016,
            weekly_return=0.0,
            monthly_return=0.0,
            state=clean_state,
        )
        assert "INTRADAY_LOSS_BLOCK" in result["triggered_rules"]
        assert "DAILY_BUY_BLOCK" not in result["triggered_rules"]

    def test_intraday_not_triggered_above_threshold(self, guard, clean_state):
        """-1.4%: intraday limit보다 미달 → INTRADAY_LOSS_BLOCK 없음."""
        result = guard.evaluate(
            daily_return=-0.014,
            weekly_return=0.0,
            monthly_return=0.0,
            state=clean_state,
        )
        assert "INTRADAY_LOSS_BLOCK" not in result["triggered_rules"]


# ── 테스트 5: cooldown 경과 후 자동 해제 ─────────────────────────────────────
class TestCooldown:
    def test_cooldown_active_blocks_buys(self, guard):
        """cooldown 기간 중 → COOLDOWN_ACTIVE, 신규 매수 불가."""
        state = DrawdownGuardState(cooldown_until="2026-04-25")
        result = guard.evaluate(
            daily_return=0.01,
            weekly_return=0.02,
            monthly_return=0.03,
            as_of="2026-04-21",
            state=state,
        )
        assert result["allow_new_buys"] is False
        assert "COOLDOWN_ACTIVE" in result["triggered_rules"]

    def test_cooldown_expired_allows_buys(self, guard):
        """cooldown 만료 후 → 신규 매수 허용 (손실 없음 가정)."""
        state = DrawdownGuardState(cooldown_until="2026-04-20")
        result = guard.evaluate(
            daily_return=0.01,
            weekly_return=0.02,
            monthly_return=0.03,
            as_of="2026-04-21",
            state=state,
        )
        assert result["allow_new_buys"] is True
        assert "COOLDOWN_ACTIVE" not in result["triggered_rules"]

    def test_cooldown_exact_expiry_date_still_blocked(self, guard):
        """cooldown_until 당일(==)은 아직 차단 상태."""
        state = DrawdownGuardState(cooldown_until="2026-04-21")
        result = guard.evaluate(
            daily_return=0.01,
            weekly_return=0.02,
            monthly_return=0.03,
            as_of="2026-04-21",
            state=state,
        )
        # now <= c_until → 여전히 차단
        assert result["allow_new_buys"] is False
        assert "COOLDOWN_ACTIVE" in result["triggered_rules"]


# ── 테스트 6: Supabase store mock 검증 ───────────────────────────────────────
class TestStoreIntegration:
    def test_store_load_called_when_market_given(self):
        """market 지정 시 store.load()가 호출된다."""
        mock_store = MagicMock()
        mock_store.load.return_value = {
            "cooldown_until": None,
            "last_action": "NONE",
            "triggered_rules": [],
        }
        guard = DrawdownGuard(store=mock_store)
        guard.evaluate(
            daily_return=0.0,
            weekly_return=0.0,
            monthly_return=0.0,
            market="btc",
        )
        mock_store.load.assert_called_once_with("btc")

    def test_store_save_called_after_evaluate(self):
        """evaluate 후 store.save()가 호출된다."""
        mock_store = MagicMock()
        mock_store.load.return_value = {
            "cooldown_until": None,
            "last_action": "NONE",
            "triggered_rules": [],
        }
        guard = DrawdownGuard(store=mock_store)
        guard.evaluate(
            daily_return=-0.03,
            weekly_return=-0.06,
            monthly_return=-0.11,
            market="kr",
        )
        mock_store.save.assert_called_once()
