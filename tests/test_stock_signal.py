from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def stock_agent(monkeypatch, mock_supabase):
    fake_kiwoom_module = types.SimpleNamespace(KiwoomClient=lambda: types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "kiwoom_client", fake_kiwoom_module)
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OPENCLAW_LOG_DIR", str(log_dir))
    sys.modules.pop("stocks.stock_trading_agent", None)
    sys.modules.pop("common.config", None)
    try:
        import common.logger as common_logger

        common_logger._loggers.pop("stock_agent", None)
    except Exception:
        pass
    import stocks.stock_trading_agent as agent

    agent = importlib.reload(agent)
    monkeypatch.setattr(agent, "supabase", mock_supabase)
    monkeypatch.setattr(agent, "_apply_kr_drift_gate", lambda signal: signal)
    return agent


def test_rule_based_signal_returns_valid_action(stock_agent):
    signal = stock_agent.rule_based_signal(
        indicators={"rsi": 38, "macd": 1, "macd_histogram": 1, "vol_ratio": 1.5, "bb_pos": 20},
        kospi={"rsi": 45},
        weekly={"trend": "UPTREND"},
        has_position=False,
        supply={"foreign_net": 1000, "inst_net": 500},
        momentum={"grade": "A", "score": 90},
        dart_score={"grade": "A", "score": 90},
    )
    assert signal["action"] in {"BUY", "SELL", "HOLD"}, f"unexpected action: {signal}"


def test_rule_based_signal_sell_on_extreme_overbought(stock_agent):
    signal = stock_agent.rule_based_signal(
        indicators={"rsi": 85, "macd": -1, "macd_histogram": -1, "vol_ratio": 1.0, "bb_pos": 95},
        kospi={"rsi": 50},
        weekly={"trend": "UPTREND"},
        has_position=True,
        supply={"foreign_net": 0, "inst_net": 0},
        momentum={"grade": "D", "score": 10},
        dart_score={"grade": "B", "score": 60},
    )
    assert signal["action"] == "SELL", f"expected SELL for overbought input, got {signal}"


def test_rule_based_signal_buy_on_extreme_oversold(stock_agent):
    signal = stock_agent.rule_based_signal(
        indicators={"rsi": 18, "macd": 1, "macd_histogram": 1, "vol_ratio": 2.2, "bb_pos": 5},
        kospi={"rsi": 30},
        weekly={"trend": "UPTREND"},
        has_position=False,
        supply={"foreign_net": 3000, "inst_net": 2000},
        momentum={"grade": "A", "score": 95},
        dart_score={"grade": "A", "score": 95},
    )
    assert signal["action"] == "BUY", f"expected BUY for oversold input, got {signal}"


def test_rule_based_signal_applies_regime_factor_adjustment(stock_agent):
    stock_agent._regime_adj_cache = {"momentum_mult": 1.0, "value_mult": 1.0, "quality_mult": 1.0}
    base = stock_agent.rule_based_signal(
        indicators={"rsi": 35, "macd": 1, "macd_histogram": 1, "vol_ratio": 1.2, "bb_pos": 25},
        kospi={"rsi": 40},
        weekly={"trend": "UPTREND"},
        has_position=False,
        supply={"foreign_net": 100, "inst_net": 100},
        momentum={"grade": "B", "score": 75},
        dart_score={"grade": "B", "score": 70},
    )
    stock_agent._regime_adj_cache = {"momentum_mult": 1.5, "value_mult": 1.0, "quality_mult": 1.5}
    boosted = stock_agent.rule_based_signal(
        indicators={"rsi": 35, "macd": 1, "macd_histogram": 1, "vol_ratio": 1.2, "bb_pos": 25},
        kospi={"rsi": 40},
        weekly={"trend": "UPTREND"},
        has_position=False,
        supply={"foreign_net": 100, "inst_net": 100},
        momentum={"grade": "B", "score": 75},
        dart_score={"grade": "B", "score": 70},
    )
    assert boosted["confidence"] >= base["confidence"], "regime factor adjustment should not reduce confidence"


def test_get_trading_signal_blends_rule_and_ml(stock_agent, monkeypatch, tmp_path):
    horizon_dir = tmp_path / "horizon_3d"
    horizon_dir.mkdir()
    fake_ml = types.SimpleNamespace(
        MODEL_DIR=tmp_path,
        get_ml_signal=lambda _code: {"confidence": 90.0, "source": "ML", "features": {}, "action": "HOLD"},
    )
    monkeypatch.setitem(sys.modules, "ml_model", fake_ml)
    monkeypatch.setattr(
        stock_agent,
        "analyze_with_ai",
        lambda *args, **kwargs: {"action": "BUY", "confidence": 70.0, "reason": "ai"},
    )

    signal = stock_agent.get_trading_signal(
        stock={"code": "005930", "name": "Samsung"},
        indicators={},
        strategy={},
        news="",
        weekly={},
        kospi={},
        has_position=False,
        supply={},
    )
    assert signal["confidence"] == 78.0, f"expected 60/40 blend to be 78.0, got {signal}"


def test_get_trading_signal_falls_back_to_rule_only(stock_agent, monkeypatch):
    monkeypatch.delitem(sys.modules, "ml_model", raising=False)
    monkeypatch.setattr(stock_agent, "analyze_with_ai", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        stock_agent,
        "rule_based_signal",
        lambda *args, **kwargs: {"action": "HOLD", "confidence": 33, "reason": "rule"},
    )
    signal = stock_agent.get_trading_signal(
        stock={"code": "005930", "name": "Samsung"},
        indicators={},
        strategy={},
        news="",
        weekly={},
        kospi={},
        has_position=False,
        supply={},
    )
    assert signal["confidence"] == 33, f"expected rule fallback confidence, got {signal}"


def test_check_daily_loss_returns_true_on_limit_breach(stock_agent, mock_telegram):
    stock_agent.send_telegram = mock_telegram
    stock_agent.supabase.table.return_value.execute.return_value.data = [
        {"price": 90, "entry_price": 100, "quantity": 10},
    ]
    assert stock_agent.check_daily_loss() is True, "daily loss breach should block trading"


def test_check_daily_loss_returns_false_below_limit(stock_agent, mock_telegram):
    stock_agent.send_telegram = mock_telegram
    stock_agent.supabase.table.return_value.execute.return_value.data = [
        {"price": 99, "entry_price": 100, "quantity": 10},
    ]
    assert stock_agent.check_daily_loss() is False, "small loss should not block trading"


def test_check_daily_loss_uses_kst_date_boundary(stock_agent):
    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 10, 23, 59, tzinfo=tz)

    stock_agent.supabase.table.return_value.execute.return_value.data = []
    stock_agent.datetime = FakeDateTime
    stock_agent.check_daily_loss()
    late_call = stock_agent.supabase.table.return_value.gte.call_args[0][1]

    class NextDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 11, 0, 1, tzinfo=tz)

    stock_agent.supabase.table.return_value.gte.reset_mock()
    stock_agent.datetime = NextDateTime
    stock_agent.check_daily_loss()
    next_call = stock_agent.supabase.table.return_value.gte.call_args[0][1]

    assert late_call != next_call, f"KST day boundary should change query start: {late_call} vs {next_call}"
