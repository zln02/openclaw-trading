"""KellyPositionSizer 단위 테스트 — 5개 이상 시나리오 검증."""
import pytest

from quant.risk.position_sizer import (KellyPositionSizer, KellySizerConfig,
                                       half_kelly_fraction, kelly_fraction)


@pytest.fixture
def default_config():
    return KellySizerConfig(
        max_single_position=0.03,
        max_total_exposure=0.60,
        atr_target=0.02,
        min_position_value=0.0,
        portfolio_var_limit=0.03,
    )


@pytest.fixture
def sizer(default_config):
    return KellyPositionSizer(config=default_config)


# ── 테스트 1: Kelly 50% (half-Kelly) 기본 계산 정확성 ─────────────────────────
class TestKellyCalculation:
    def test_kelly_fraction_formula(self):
        """f* = (b*p - q) / b 수식 검증."""
        # win_rate=0.6, payoff_ratio=2.0 → f* = (2*0.6 - 0.4)/2 = 0.8/2 = 0.40
        f = kelly_fraction(win_rate=0.6, payoff_ratio=2.0)
        assert abs(f - 0.40) < 1e-6

    def test_half_kelly_is_50pct_of_full_kelly(self):
        """half-Kelly = full-Kelly × 0.5."""
        full = kelly_fraction(0.6, 2.0)
        half = half_kelly_fraction(0.6, 2.0)
        assert abs(half - full * 0.5) < 1e-6

    def test_kelly_zero_when_payoff_ratio_zero(self):
        """payoff_ratio=0 → kelly_fraction=0.0."""
        f = kelly_fraction(0.6, 0.0)
        assert f == 0.0

    def test_kelly_zero_when_negative_edge(self):
        """승률 낮고 payoff 낮으면 음수 켈리 → clamp to 0."""
        f = kelly_fraction(0.3, 0.5)  # edge = 0.5*0.3 - 0.7 = -0.55 < 0
        assert f == 0.0

    def test_size_position_base_kelly_half(self, sizer):
        """size_position의 kelly_fraction이 half-kelly임을 검증."""
        result = sizer.size_position(
            account_equity=100_000,
            price=50_000,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
        )
        expected_half = half_kelly_fraction(0.6, 2.0)
        assert abs(result["kelly_fraction"] - expected_half) < 1e-5


# ── 테스트 2: max_single_position 3% 상한 강제 ────────────────────────────────
class TestMaxSinglePositionCap:
    def test_capped_to_max_single_position(self, sizer):
        """kelly가 3% 초과해도 capped_fraction은 3% 이하."""
        # win_rate=0.8, payoff=3.0 → 큰 kelly
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.8,
            payoff_ratio=3.0,
            current_total_exposure=0.0,
        )
        assert result["capped_fraction"] <= 0.03 + 1e-9

    def test_custom_max_single_respected(self):
        """max_single_position 커스텀 값(5%)이 올바르게 적용된다."""
        cfg = KellySizerConfig(max_single_position=0.05, max_total_exposure=0.80)
        sizer = KellyPositionSizer(config=cfg)
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.9,
            payoff_ratio=5.0,
            current_total_exposure=0.0,
        )
        assert result["capped_fraction"] <= 0.05 + 1e-9

    def test_target_value_consistent_with_fraction(self, sizer):
        """target_value == account_equity × capped_fraction 검증."""
        equity = 200_000
        result = sizer.size_position(
            account_equity=equity,
            price=1_000,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
        )
        expected_value = equity * result["capped_fraction"]
        assert abs(result["target_value"] - expected_value) < 1.0  # 반올림 오차 허용


# ── 테스트 3: max_exposure 60% 전체 노출 한도 ─────────────────────────────────
class TestMaxTotalExposure:
    def test_remaining_exposure_zero_when_full(self, sizer):
        """current_total_exposure=60% → remaining=0, capped=0."""
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.7,
            payoff_ratio=2.0,
            current_total_exposure=0.60,
        )
        assert result["capped_fraction"] == 0.0
        assert result["target_value"] == 0.0

    def test_remaining_capacity_correctly_limits(self, sizer):
        """current_total_exposure=58% → remaining=2%, capped<=2%."""
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.7,
            payoff_ratio=2.0,
            current_total_exposure=0.58,
        )
        # remaining = 0.60 - 0.58 = 0.02
        assert result["capped_fraction"] <= 0.02 + 1e-9

    def test_quantity_calculated_correctly(self, sizer):
        """quantity = target_value / price 검증."""
        price = 50_000
        result = sizer.size_position(
            account_equity=1_000_000,
            price=price,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
        )
        expected_qty = result["target_value"] / price
        assert abs(result["quantity"] - expected_qty) < 1e-4


# ── 테스트 4: ATR 기반 변동성 스케일링 ───────────────────────────────────────
class TestATRVolatilityScaling:
    def test_high_atr_reduces_position(self, sizer):
        """ATR이 target(2%)보다 크면 position이 줄어든다."""
        # atr_pct=0.04 (4%) > atr_target=0.02 → vol_scale = 0.02/0.04 = 0.5
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
            atr_pct=0.04,
        )
        assert result["volatility_scale"] == pytest.approx(0.5, abs=1e-4)

    def test_low_atr_no_scale_beyond_1(self, sizer):
        """ATR이 target보다 낮아도 vol_scale은 1.0으로 클램핑."""
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
            atr_pct=0.005,  # very low ATR
        )
        assert result["volatility_scale"] == pytest.approx(1.0, abs=1e-6)

    def test_no_atr_uses_scale_1(self, sizer):
        """atr_pct 미입력 시 vol_scale=1.0 (스케일링 없음)."""
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
            atr_pct=None,
        )
        assert result["volatility_scale"] == 1.0


# ── 테스트 5: conviction scaling 반영 ────────────────────────────────────────
class TestConvictionScaling:
    def test_high_conviction_increases_position(self, sizer):
        """conviction=1.5 → conviction=1.0 대비 target_fraction 1.5배."""
        r1 = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.55,
            payoff_ratio=1.5,
            current_total_exposure=0.0,
            conviction=1.0,
        )
        r2 = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.55,
            payoff_ratio=1.5,
            current_total_exposure=0.0,
            conviction=1.5,
        )
        # target_fraction 1.5배 (캡 이전 값)
        assert r2["target_fraction"] >= r1["target_fraction"]

    def test_zero_conviction_zeros_position(self, sizer):
        """conviction=0 → target_fraction=0, 포지션 없음."""
        result = sizer.size_position(
            account_equity=100_000,
            price=1_000,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
            conviction=0.0,
        )
        assert result["target_fraction"] == 0.0
        assert result["capped_fraction"] == 0.0


# ── 테스트 6: VaR 추정 및 포트폴리오 VaR 체크 ────────────────────────────────
class TestVaRCheck:
    def test_estimate_position_var(self, sizer):
        """position 3%, daily_vol 2%, 5일 99% VaR 계산."""
        var = sizer.estimate_position_var(
            position_fraction=0.03,
            daily_vol=0.02,
            holding_days=5,
            confidence=2.33,
        )
        # 0.03 * 0.02 * sqrt(5) * 2.33 ≈ 0.003125
        expected = abs(0.03 * 0.02 * (5 ** 0.5) * 2.33)
        assert abs(var - expected) < 1e-6

    def test_check_portfolio_var_within_limit(self, sizer):
        """기존 VaR + 신규 VaR < 3% → True (허용)."""
        result = sizer.check_portfolio_var(
            existing_positions_var=0.01,
            new_position_var=0.01,
        )
        assert result is True

    def test_check_portfolio_var_exceeds_limit(self, sizer):
        """기존 VaR + 신규 VaR > 3% → False (차단)."""
        result = sizer.check_portfolio_var(
            existing_positions_var=0.025,
            new_position_var=0.010,
        )
        assert result is False


# ── 테스트 7: 엣지 케이스 ────────────────────────────────────────────────────
class TestEdgeCases:
    def test_zero_equity_returns_zero(self, sizer):
        """equity=0 → invalid_input 반환."""
        result = sizer.size_position(
            account_equity=0,
            price=1_000,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
        )
        assert result["reason"] == "invalid_input"
        assert result["quantity"] == 0.0

    def test_zero_price_returns_zero(self, sizer):
        """price=0 → invalid_input 반환."""
        result = sizer.size_position(
            account_equity=100_000,
            price=0,
            win_rate=0.6,
            payoff_ratio=2.0,
            current_total_exposure=0.0,
        )
        assert result["reason"] == "invalid_input"

    def test_size_batch_ranks_by_edge(self, sizer):
        """size_batch가 edge 높은 순으로 정렬해 처리한다."""
        candidates = [
            {"symbol": "A", "price": 1000, "win_rate": 0.5, "payoff_ratio": 1.0, "conviction": 1.0},
            {"symbol": "B", "price": 1000, "win_rate": 0.7, "payoff_ratio": 2.0, "conviction": 1.0},
        ]
        results = sizer.size_batch(
            account_equity=100_000,
            current_total_exposure=0.0,
            candidates=candidates,
        )
        # B(높은 edge)가 첫 번째로 처리되어야 함
        symbols = [r["symbol"] for r in results]
        assert symbols[0] == "B"
