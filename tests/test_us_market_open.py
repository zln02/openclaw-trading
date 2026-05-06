"""Tests for stocks.us_stock_trading_agent.is_us_market_open (KST 기반).

Background: 2026-03 의 UTC 버그 (datetime.now(timezone.utc)) 로 RTH 포함 항상
False 반환했던 문제 재발 방지. KR 의 e9b0fb59b 동일 패턴 — 시각은 KST 기반,
미국장은 KST 23:30~06:00 으로 근사.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

KST = timezone(timedelta(hours=9))


class _FrozenDatetime(datetime):
    """datetime.now(tz) 결과를 _frozen 으로 고정."""

    _frozen: datetime = datetime(2026, 5, 6, 0, 0, tzinfo=KST)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._frozen
        return cls._frozen.astimezone(tz)


def _freeze(dt: datetime):
    _FrozenDatetime._frozen = dt
    return patch("stocks.us_stock_trading_agent.datetime", _FrozenDatetime)


def test_kst_2330_returns_true():
    """KST 23:30 — RTH 시작 (h=23 → True)."""
    with _freeze(datetime(2026, 5, 6, 23, 30, tzinfo=KST)):
        from stocks.us_stock_trading_agent import is_us_market_open
        assert is_us_market_open() is True


def test_kst_0030_returns_true():
    """KST 00:30 — RTH 중간 (h=0 < 6 → True)."""
    with _freeze(datetime(2026, 5, 6, 0, 30, tzinfo=KST)):
        from stocks.us_stock_trading_agent import is_us_market_open
        assert is_us_market_open() is True


def test_kst_0500_returns_true():
    """KST 05:00 — RTH 후반 (h=5 < 6 → True)."""
    with _freeze(datetime(2026, 5, 6, 5, 0, tzinfo=KST)):
        from stocks.us_stock_trading_agent import is_us_market_open
        assert is_us_market_open() is True


def test_kst_0600_returns_false():
    """KST 06:00 — RTH 종료 boundary (h=6, h<6 False, h>=23 False → False)."""
    with _freeze(datetime(2026, 5, 6, 6, 0, tzinfo=KST)):
        from stocks.us_stock_trading_agent import is_us_market_open
        assert is_us_market_open() is False


def test_kst_1200_returns_false():
    """KST 정오 — 명백한 장 외."""
    with _freeze(datetime(2026, 5, 6, 12, 0, tzinfo=KST)):
        from stocks.us_stock_trading_agent import is_us_market_open
        assert is_us_market_open() is False


def test_kst_2200_returns_false():
    """KST 22:00 — RTH 시작 1시간 전 (h=22, h>=23 False)."""
    with _freeze(datetime(2026, 5, 6, 22, 0, tzinfo=KST)):
        from stocks.us_stock_trading_agent import is_us_market_open
        assert is_us_market_open() is False


def test_uses_kst_not_utc():
    """KST 04:00 (= UTC 전날 19:00) — KST 기반이면 True (h=4<6).
    UTC 기반(옛 버그)이면 h=19, h>=23 False, h<6 False → False.
    회귀 가드: KST 기반 결과만 검증."""
    with _freeze(datetime(2026, 5, 6, 4, 0, tzinfo=KST)):
        from stocks.us_stock_trading_agent import is_us_market_open
        assert is_us_market_open() is True
