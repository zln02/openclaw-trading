"""Tests for common.health cron freshness check (supabase btc_trades 신호)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from common.health import _last_btc_trade_ts, check_cron_freshness


def _utc(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _supabase_with_rows(rows):
    sb = MagicMock()
    chain = sb.table.return_value
    chain = chain.select.return_value
    chain = chain.order.return_value
    chain = chain.limit.return_value
    chain.execute.return_value = MagicMock(data=rows)
    return sb


# ────────────────────────────────────────────────────────────────────────────
# _last_btc_trade_ts
# ────────────────────────────────────────────────────────────────────────────

class TestLastBtcTradeTs:
    def test_returns_parsed_datetime(self):
        sb = _supabase_with_rows([{"timestamp": "2026-04-27T02:30:00+00:00"}])
        ts = _last_btc_trade_ts(sb)
        assert ts == _utc(2026, 4, 27, 2, 30)

    def test_handles_z_suffix(self):
        sb = _supabase_with_rows([{"timestamp": "2026-04-27T02:30:00Z"}])
        ts = _last_btc_trade_ts(sb)
        assert ts == _utc(2026, 4, 27, 2, 30)

    def test_returns_none_when_empty(self):
        sb = _supabase_with_rows([])
        assert _last_btc_trade_ts(sb) is None

    def test_returns_none_when_timestamp_missing(self):
        sb = _supabase_with_rows([{"timestamp": None}])
        assert _last_btc_trade_ts(sb) is None


# ────────────────────────────────────────────────────────────────────────────
# check_cron_freshness — BTC 사이클 신호
# ────────────────────────────────────────────────────────────────────────────

class _FrozenDatetime(datetime):
    _frozen: datetime = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls._frozen if tz is None else cls._frozen.astimezone(tz)


def _freeze_now(now_utc: datetime):
    _FrozenDatetime._frozen = now_utc
    return patch("common.health.datetime", _FrozenDatetime)


def test_freshness_healthy_btc_5min_ago():
    now_utc = _utc(2026, 4, 27, 12, 0)
    btc_ts = (now_utc - timedelta(minutes=5)).isoformat()
    sb = _supabase_with_rows([{"timestamp": btc_ts}])

    with _freeze_now(now_utc), patch("common.health.get_supabase", return_value=sb):
        result = asyncio.run(check_cron_freshness())

    assert result["source"] == "supabase.btc_trades"
    assert result["btc"]["age_minutes"] == 5
    assert result["kr"]["signal"] == "not_tracked"
    assert result["us"]["signal"] == "not_tracked"


def test_freshness_stale_btc_raises():
    now_utc = _utc(2026, 4, 27, 12, 0)
    btc_ts = (now_utc - timedelta(minutes=60)).isoformat()
    sb = _supabase_with_rows([{"timestamp": btc_ts}])

    with _freeze_now(now_utc), patch("common.health.get_supabase", return_value=sb):
        with pytest.raises(RuntimeError, match="BTC 사이클 정체"):
            asyncio.run(check_cron_freshness())


def test_freshness_empty_table_raises():
    sb = _supabase_with_rows([])

    with patch("common.health.get_supabase", return_value=sb):
        with pytest.raises(RuntimeError, match="btc_trades 테이블에 데이터가 없습니다"):
            asyncio.run(check_cron_freshness())


def test_freshness_supabase_unavailable():
    with patch("common.health.get_supabase", return_value=None):
        with pytest.raises(RuntimeError, match="Supabase 클라이언트 미초기화"):
            asyncio.run(check_cron_freshness())


def test_freshness_at_30min_boundary_passes():
    now_utc = _utc(2026, 4, 27, 12, 0)
    btc_ts = (now_utc - timedelta(minutes=30)).isoformat()
    sb = _supabase_with_rows([{"timestamp": btc_ts}])

    with _freeze_now(now_utc), patch("common.health.get_supabase", return_value=sb):
        result = asyncio.run(check_cron_freshness())
    assert result["btc"]["age_minutes"] == 30
