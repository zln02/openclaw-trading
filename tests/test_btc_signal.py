from __future__ import annotations

from datetime import datetime

import pytest

from btc import btc_trading_agent as agent


def test_calc_btc_composite_returns_score_in_range():
    out = agent.calc_btc_composite(
        fg_value=20,
        rsi_d=35,
        bb_pct=15,
        vol_ratio_d=1.5,
        trend="UPTREND",
        ret_7d=-8,
    )
    assert 0 <= out["total"] <= 100, f"composite score must be clamped to 0~100: {out}"


def test_calc_btc_composite_applies_regime_adjustment():
    bull = agent.calc_btc_composite(20, 35, 15, 1.5, "UPTREND", regime="RISK_ON")
    bear = agent.calc_btc_composite(20, 35, 15, 1.5, "UPTREND", regime="RISK_OFF")
    assert bull["total"] > bear["total"], f"risk-on regime should score higher: {bull} vs {bear}"


def test_calc_btc_composite_reflects_whale_signal():
    neutral = agent.calc_btc_composite(20, 35, 15, 1.5, "UPTREND", whale={"signal": "NEUTRAL"})
    hodl = agent.calc_btc_composite(20, 35, 15, 1.5, "UPTREND", whale={"signal": "HODL_SIGNAL"})
    assert hodl["total"] >= neutral["total"], f"whale hodl signal should not reduce score: {hodl} vs {neutral}"


def test_btc_check_daily_loss_uses_kst_boundary(mock_supabase, monkeypatch):
    monkeypatch.setattr(agent, "supabase", mock_supabase)
    mock_supabase.table.return_value.execute.return_value.data = []

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 10, 23, 59, tzinfo=tz)

    monkeypatch.setattr(agent, "datetime", FakeDateTime)
    agent.check_daily_loss()
    late_call = mock_supabase.table.return_value.gte.call_args[0][1]

    class NextDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 11, 0, 1, tzinfo=tz)

    mock_supabase.table.return_value.gte.reset_mock()
    monkeypatch.setattr(agent, "datetime", NextDateTime)
    agent.check_daily_loss()
    next_call = mock_supabase.table.return_value.gte.call_args[0][1]

    assert late_call != next_call, f"BTC daily loss should roll over on KST day boundary: {late_call} vs {next_call}"


def test_upbit_call_retries_on_429(monkeypatch):
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise Exception("429 too many requests")
        return "ok"

    result = agent._upbit_call(flaky, max_retries=3)
    assert result == "ok", "429 path should eventually return successful result"
    assert calls["count"] == 3, f"expected 3 attempts, got {calls['count']}"


def test_upbit_call_raises_on_non_429():
    with pytest.raises(Exception, match="boom"):
        agent._upbit_call(lambda: (_ for _ in ()).throw(Exception("boom")), max_retries=3)
