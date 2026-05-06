"""Tests for WeeklyAttributionRunner BTC 확장 (btc_trades 통합)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from quant.portfolio.attribution import WeeklyAttributionRunner

# ────────────────────────────────────────────────────────────────────────────
# Mock helpers
# ────────────────────────────────────────────────────────────────────────────

def _supabase_with_btc_rows(rows):
    """btc_trades 의 .table().select().in_().gte().order().execute() chain mock."""
    sb = MagicMock()
    chain = sb.table.return_value
    chain = chain.select.return_value
    chain = chain.in_.return_value
    chain = chain.gte.return_value
    chain = chain.order.return_value
    chain.execute.return_value = MagicMock(data=rows)
    return sb


def _btc_row(action: str, price: float, snapshot: dict | str | None, ts: str = "2026-05-06T00:00:00Z"):
    return {
        "id": 1,
        "timestamp": ts,
        "action": action,
        "price": price,
        "indicator_snapshot": snapshot,
    }


# ────────────────────────────────────────────────────────────────────────────
# _load_btc_trades
# ────────────────────────────────────────────────────────────────────────────

class TestLoadBtcTrades:
    def test_pairs_buy_sell_calculates_pnl(self):
        rows = [
            _btc_row("BUY", 100_000_000.0, {"rsi": 30, "macd": -0.5}, "2026-05-01T00:00:00Z"),
            _btc_row("SELL", 110_000_000.0, {"rsi": 70, "macd": 1.0}, "2026-05-02T00:00:00Z"),
        ]
        runner = WeeklyAttributionRunner(supabase_client=_supabase_with_btc_rows(rows))
        result = runner._load_btc_trades(lookback_days=7)
        assert len(result) == 1
        assert result[0]["pnl_pct"] == 10.0  # (110 - 100) / 100 * 100
        assert result[0]["factors"] == {"rsi": 30, "macd": -0.5}  # BUY 시점 신호
        assert result[0]["market"] == "btc"

    def test_unmatched_buy_returns_open_trade_pnl_zero(self):
        """BUY 만 있고 SELL 매칭 없으면 KR OPEN row 패턴 모방 — pnl=0 으로 포함."""
        rows = [_btc_row("BUY", 100_000_000.0, {"rsi": 30}, "2026-05-01T00:00:00Z")]
        runner = WeeklyAttributionRunner(supabase_client=_supabase_with_btc_rows(rows))
        result = runner._load_btc_trades(lookback_days=7)
        assert len(result) == 1
        assert result[0]["pnl_pct"] == 0.0
        assert result[0]["factors"] == {"rsi": 30}
        assert result[0]["market"] == "btc"
        # _buy_price 임시 키는 노출 안 됨
        assert "_buy_price" not in result[0]

    def test_invalid_snapshot_skipped(self):
        rows = [
            _btc_row("BUY", 100_000_000.0, None, "2026-05-01T00:00:00Z"),
            _btc_row("SELL", 110_000_000.0, "not-json-{", "2026-05-02T00:00:00Z"),
            _btc_row("BUY", 100_000_000.0, "this is not json", "2026-05-03T00:00:00Z"),
            _btc_row("SELL", 105_000_000.0, {"rsi": 50}, "2026-05-04T00:00:00Z"),
        ]
        runner = WeeklyAttributionRunner(supabase_client=_supabase_with_btc_rows(rows))
        # 처음 두 row 는 snapshot 무효 → BUY/SELL 페어 형성 안 됨. 세 번째도 string non-json → skip
        # 네 번째는 SELL 인데 매칭 BUY 없음
        assert runner._load_btc_trades(lookback_days=7) == []

    def test_zero_buy_price_skipped(self):
        rows = [
            _btc_row("BUY", 0.0, {"rsi": 30}, "2026-05-01T00:00:00Z"),
            _btc_row("SELL", 100_000_000.0, {"rsi": 70}, "2026-05-02T00:00:00Z"),
        ]
        runner = WeeklyAttributionRunner(supabase_client=_supabase_with_btc_rows(rows))
        assert runner._load_btc_trades(lookback_days=7) == []

    def test_handles_json_string_snapshot(self):
        rows = [
            _btc_row("BUY", 100_000_000.0, json.dumps({"rsi": 30, "macd": -0.5}), "2026-05-01T00:00:00Z"),
            _btc_row("SELL", 105_000_000.0, json.dumps({"rsi": 60}), "2026-05-02T00:00:00Z"),
        ]
        runner = WeeklyAttributionRunner(supabase_client=_supabase_with_btc_rows(rows))
        result = runner._load_btc_trades(lookback_days=7)
        assert len(result) == 1
        assert result[0]["pnl_pct"] == 5.0
        assert result[0]["factors"] == {"rsi": 30, "macd": -0.5}

    def test_supabase_unavailable_returns_empty(self):
        runner = WeeklyAttributionRunner(supabase_client=None)
        runner.supabase = None  # 강제 None
        assert runner._load_btc_trades(lookback_days=7) == []


# ────────────────────────────────────────────────────────────────────────────
# run() — KR + BTC 통합
# ────────────────────────────────────────────────────────────────────────────

def test_run_no_data_when_both_empty(monkeypatch):
    runner = WeeklyAttributionRunner(supabase_client=MagicMock())
    monkeypatch.setattr(runner, "_load_closed_trades", lambda lookback_days: [])
    monkeypatch.setattr(runner, "_load_btc_trades", lambda lookback_days: [])
    monkeypatch.setattr(runner, "_send_report", lambda *a, **kw: None)

    result = runner.run(dry_run=True)
    assert result["status"] == "NO_DATA"
    assert result["n_trades"] == 0
    assert result["market_distribution"] == {"kr": 0, "btc": 0}


def test_run_ok_when_btc_only_kr_empty(monkeypatch):
    runner = WeeklyAttributionRunner(supabase_client=MagicMock())
    monkeypatch.setattr(runner, "_load_closed_trades", lambda lookback_days: [])
    monkeypatch.setattr(runner, "_load_btc_trades", lambda lookback_days: [
        {"pnl_pct": 5.0, "factors": {"rsi": 30, "macd": -0.5}, "market": "btc"},
        {"pnl_pct": -2.0, "factors": {"rsi": 70, "macd": 1.0}, "market": "btc"},
    ])
    monkeypatch.setattr(runner, "_send_report", lambda *a, **kw: None)

    result = runner.run(dry_run=True)
    assert result["status"] == "OK"
    assert result["n_trades"] == 2
    assert result["market_distribution"] == {"kr": 0, "btc": 2}
    assert "factor_attribution" in result
    # rsi/macd factor 별 contribution 계산됐는지
    assert "rsi" in result["factor_attribution"]
    assert "macd" in result["factor_attribution"]


def test_buy_only_appears_in_market_distribution(monkeypatch):
    """BTC BUY 만 (SELL 0건) 패턴에서도 attribution 활성화 — KR 0 + BTC OPEN trades."""
    runner = WeeklyAttributionRunner(supabase_client=MagicMock())
    monkeypatch.setattr(runner, "_load_closed_trades", lambda lookback_days: [])
    monkeypatch.setattr(runner, "_load_btc_trades", lambda lookback_days: [
        {"pnl_pct": 0.0, "factors": {"rsi": 30, "macd": -0.5}, "market": "btc"},
        {"pnl_pct": 0.0, "factors": {"rsi": 35, "macd": -0.3}, "market": "btc"},
        {"pnl_pct": 0.0, "factors": {"rsi": 25, "macd": -1.0}, "market": "btc"},
    ])
    monkeypatch.setattr(runner, "_send_report", lambda *a, **kw: None)

    result = runner.run(dry_run=True)
    assert result["status"] == "OK"  # NO_DATA 아님
    assert result["n_trades"] == 3
    assert result["market_distribution"] == {"kr": 0, "btc": 3}
    # pnl=0 이어도 factor_attribution dict 는 채워져야 (factor 노출 추적)
    assert "rsi" in result["factor_attribution"]
    assert "macd" in result["factor_attribution"]
    # 모든 trade 의 pnl=0 이라 contribution=0
    assert result["factor_attribution"]["rsi"]["total_contrib"] == 0.0
    assert result["total_pnl_avg"] == 0.0


def test_run_market_distribution_with_kr_and_btc(monkeypatch):
    runner = WeeklyAttributionRunner(supabase_client=MagicMock())
    monkeypatch.setattr(runner, "_load_closed_trades", lambda lookback_days: [
        {"pnl_pct": 3.0, "factors": {"rsi": 25}, "market": "kr"},
    ])
    monkeypatch.setattr(runner, "_load_btc_trades", lambda lookback_days: [
        {"pnl_pct": 5.0, "factors": {"rsi": 30}, "market": "btc"},
        {"pnl_pct": -1.0, "factors": {"rsi": 60}, "market": "btc"},
    ])
    monkeypatch.setattr(runner, "_send_report", lambda *a, **kw: None)

    result = runner.run(dry_run=True)
    assert result["status"] == "OK"
    assert result["n_trades"] == 3
    assert result["market_distribution"] == {"kr": 1, "btc": 2}
    assert result["total_pnl_avg"] == round((3.0 + 5.0 - 1.0) / 3, 4)
