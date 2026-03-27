from __future__ import annotations

from quant.risk.correlation_monitor import check_concentration_risk
from quant.risk.drawdown_guard import DrawdownGuard, DrawdownGuardState
from quant.risk.position_sizer import KellyPositionSizer, KellySizerConfig


def test_drawdown_guard_blocks_on_daily_limit():
    guard = DrawdownGuard()
    out = guard.evaluate(daily_return=-0.03, weekly_return=0.0, monthly_return=0.0)
    assert out["allow_new_buys"] is False, f"daily limit breach should block new buys: {out}"
    assert "DAILY_BUY_BLOCK" in out["triggered_rules"], f"expected daily block trigger: {out}"


def test_drawdown_guard_blocks_during_cooldown():
    guard = DrawdownGuard()
    state = DrawdownGuardState(cooldown_until="2099-01-01", last_action="MONTHLY_STOP")
    out = guard.evaluate(daily_return=0.0, weekly_return=0.0, monthly_return=0.0, state=state)
    assert out["allow_new_buys"] is False, f"cooldown should block buys: {out}"
    assert "COOLDOWN_ACTIVE" in out["triggered_rules"], f"expected cooldown trigger: {out}"


def test_drawdown_guard_allows_normal_state():
    guard = DrawdownGuard()
    out = guard.evaluate(daily_return=0.01, weekly_return=0.02, monthly_return=0.03)
    assert out["allow_new_buys"] is True, f"healthy state should allow buys: {out}"


def test_kelly_position_size_within_bounds():
    sizer = KellyPositionSizer()
    out = sizer.size_position(
        account_equity=100000,
        price=100,
        win_rate=0.6,
        payoff_ratio=1.5,
        current_total_exposure=0.1,
        atr_pct=0.01,
    )
    assert 0 < out["capped_fraction"] <= out["max_single_position"], f"size must stay within max_single: {out}"


def test_kelly_expected_fraction_for_50_2_to_1():
    sizer = KellyPositionSizer()
    out = sizer.size_position(
        account_equity=100000,
        price=100,
        win_rate=0.5,
        payoff_ratio=2.0,
        current_total_exposure=0.0,
        atr_pct=0.02,
    )
    assert abs(out["full_kelly_fraction"] - 0.25) < 1e-6, f"expected full Kelly 0.25, got {out}"
    assert abs(out["kelly_fraction"] - 0.125) < 1e-6, f"expected half Kelly 0.125, got {out}"


def test_kelly_atr_adjustment_reduces_size():
    sizer = KellyPositionSizer(KellySizerConfig(max_single_position=0.5))
    low_atr = sizer.size_position(
        account_equity=100000,
        price=100,
        win_rate=0.6,
        payoff_ratio=1.5,
        current_total_exposure=0.0,
        atr_pct=0.01,
    )
    high_atr = sizer.size_position(
        account_equity=100000,
        price=100,
        win_rate=0.6,
        payoff_ratio=1.5,
        current_total_exposure=0.0,
        atr_pct=0.05,
    )
    assert high_atr["target_fraction"] < low_atr["target_fraction"], f"higher ATR should reduce pre-cap size: {low_atr} vs {high_atr}"
    assert high_atr["capped_fraction"] < low_atr["capped_fraction"], f"higher ATR should reduce final size when cap is relaxed: {low_atr} vs {high_atr}"


def test_correlation_monitor_high_risk(monkeypatch):
    monkeypatch.setattr(
        "quant.risk.correlation_monitor.get_btc_exposure",
        lambda: {"market": "BTC", "exposed": True, "direction": "LONG"},
    )
    monkeypatch.setattr(
        "quant.risk.correlation_monitor.get_kr_exposure",
        lambda: {"market": "KR", "exposed": True, "direction": "LONG", "count": 2, "sectors": ["tech"]},
    )
    monkeypatch.setattr(
        "quant.risk.correlation_monitor.get_us_exposure",
        lambda: {"market": "US", "exposed": True, "direction": "LONG", "count": 1, "sectors": ["ai"]},
    )
    out = check_concentration_risk()
    assert out["risk_level"] == "HIGH", f"all-long exposure should be HIGH risk: {out}"


def test_correlation_monitor_low_risk(monkeypatch):
    monkeypatch.setattr(
        "quant.risk.correlation_monitor.get_btc_exposure",
        lambda: {"market": "BTC", "exposed": True, "direction": "LONG"},
    )
    monkeypatch.setattr(
        "quant.risk.correlation_monitor.get_kr_exposure",
        lambda: {"market": "KR", "exposed": False, "direction": "NONE", "count": 0, "sectors": []},
    )
    monkeypatch.setattr(
        "quant.risk.correlation_monitor.get_us_exposure",
        lambda: {"market": "US", "exposed": False, "direction": "NONE", "count": 0, "sectors": []},
    )
    out = check_concentration_risk()
    assert out["risk_level"] == "LOW", f"single-market exposure should be LOW risk: {out}"
