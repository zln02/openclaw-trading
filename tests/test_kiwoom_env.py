"""키움 환경변수 로딩 단일 진입점 단위 테스트.

Phase 2-4 (보안 사고 처리 + P0 인프라 복구).
or-fallback 제거 + TRADING_ENV 인식 회귀 방지.
"""
from __future__ import annotations

import pytest

from common.kiwoom_env import (
    KiwoomCredentials,
    get_kiwoom_credentials,
    resolve_use_mock,
)


_KIWOOM_VARS = (
    "TRADING_ENV",
    "KIWOOM_REST_API_KEY",
    "KIWOOM_REST_API_SECRET",
    "KIWOOM_ACCOUNT_NO",
    "KIWOOM_MOCK_REST_API_APP_KEY",
    "KIWOOM_MOCK_REST_API_SECRET_KEY",
    "KIWOOM_MOCK_ACCOUNT_NO",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """각 테스트 시작 시 키움 관련 env 모두 제거."""
    for var in _KIWOOM_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def test_mock_mode_with_mock_keys(monkeypatch):
    """TRADING_ENV=mock + mock 키 set → use_mock=True, mock base_url."""
    monkeypatch.setenv("TRADING_ENV", "mock")
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_APP_KEY", "mock-app-key")
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_SECRET_KEY", "mock-secret")
    monkeypatch.setenv("KIWOOM_MOCK_ACCOUNT_NO", "5012345678")

    creds = get_kiwoom_credentials()

    assert isinstance(creds, KiwoomCredentials)
    assert creds.use_mock is True
    assert creds.api_key == "mock-app-key"
    assert creds.api_secret == "mock-secret"
    assert creds.account_no == "5012345678"
    assert creds.base_url == "https://mockapi.kiwoom.com"


def test_prod_mode_with_prod_keys(monkeypatch):
    """TRADING_ENV=prod + 실전 키 set → use_mock=False, prod base_url."""
    monkeypatch.setenv("TRADING_ENV", "prod")
    monkeypatch.setenv("KIWOOM_REST_API_KEY", "prod-key")
    monkeypatch.setenv("KIWOOM_REST_API_SECRET", "prod-secret")
    monkeypatch.setenv("KIWOOM_ACCOUNT_NO", "9012345678")

    creds = get_kiwoom_credentials()

    assert creds.use_mock is False
    assert creds.api_key == "prod-key"
    assert creds.api_secret == "prod-secret"
    assert creds.account_no == "9012345678"
    assert creds.base_url == "https://api.kiwoom.com"


def test_default_is_mock_when_trading_env_unset(monkeypatch):
    """TRADING_ENV 미설정 → 기본 mock."""
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_APP_KEY", "mock-app-key")
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_SECRET_KEY", "mock-secret")

    assert resolve_use_mock() is True

    creds = get_kiwoom_credentials()
    assert creds.use_mock is True
    assert creds.base_url == "https://mockapi.kiwoom.com"


def test_mock_mode_missing_mock_key_raises_no_fallback(monkeypatch):
    """mock 모드 + mock 키 누락 (실전 키만 있음) → ValueError.

    이전 버그(or-fallback)에서는 실전 키로 폴백돼 silent wrong-key 주입이 발생했다.
    이 테스트는 fallback이 없음을 보장한다.
    """
    monkeypatch.setenv("TRADING_ENV", "mock")
    monkeypatch.setenv("KIWOOM_REST_API_KEY", "prod-key")
    monkeypatch.setenv("KIWOOM_REST_API_SECRET", "prod-secret")
    # KIWOOM_MOCK_* 는 의도적으로 미설정

    with pytest.raises(ValueError, match="모의투자"):
        get_kiwoom_credentials()


def test_prod_mode_missing_prod_key_raises_no_fallback(monkeypatch):
    """실전 모드 + 실전 키 누락 (mock 키만 있음) → ValueError."""
    monkeypatch.setenv("TRADING_ENV", "prod")
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_APP_KEY", "mock-app-key")
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_SECRET_KEY", "mock-secret")
    # KIWOOM_REST_API_KEY/SECRET 는 의도적으로 미설정

    with pytest.raises(ValueError, match="실전투자"):
        get_kiwoom_credentials()


def test_explicit_use_mock_overrides_trading_env(monkeypatch):
    """use_mock=True 명시 인자가 TRADING_ENV=prod를 덮어쓴다."""
    monkeypatch.setenv("TRADING_ENV", "prod")
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_APP_KEY", "mock-app-key")
    monkeypatch.setenv("KIWOOM_MOCK_REST_API_SECRET_KEY", "mock-secret")

    assert resolve_use_mock(True) is True

    creds = get_kiwoom_credentials(use_mock=True)
    assert creds.use_mock is True
    assert creds.api_key == "mock-app-key"
    assert creds.base_url == "https://mockapi.kiwoom.com"
