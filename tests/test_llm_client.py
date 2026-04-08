"""common/llm_client.py 유닛테스트."""
import os
from unittest.mock import MagicMock, patch

import pytest

from common.cache import clear_cache, set_cached
from common.llm_client import _QUOTA_CACHE_KEY, call_haiku, is_quota_exceeded


@pytest.fixture(autouse=True)
def _clean_cache():
    """각 테스트 전후 캐시 초기화."""
    clear_cache()
    yield
    clear_cache()


def test_is_quota_exceeded_default_false():
    assert is_quota_exceeded() is False


def test_is_quota_exceeded_when_cached():
    set_cached(_QUOTA_CACHE_KEY, True, ttl=60)
    assert is_quota_exceeded() is True


def test_call_haiku_no_api_key():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        result = call_haiku("hello")
    assert result is None


def test_call_haiku_quota_exceeded_returns_none():
    set_cached(_QUOTA_CACHE_KEY, True, ttl=60)
    result = call_haiku("hello")
    assert result is None


@patch("common.llm_client._get_client")
def test_call_haiku_success(mock_get_client):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="BTC 상승 예상")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mock_get_client.return_value = mock_client

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        result = call_haiku("BTC 분석해줘", system="트레이더")

    assert result == "BTC 상승 예상"
    mock_client.messages.create.assert_called_once()
