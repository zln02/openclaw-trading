"""공용 Claude Haiku 클라이언트 래퍼.

Usage:
    from common.llm_client import call_haiku, is_quota_exceeded

    result = call_haiku("BTC 분석해줘", system="당신은 퀀트 트레이더입니다.")
    if result is None:
        # quota 초과 또는 API 에러 → fallback
"""
from __future__ import annotations

import os
from typing import Optional

from common.cache import get_cached, set_cached
from common.logger import get_logger

log = get_logger("llm_client")

_QUOTA_CACHE_KEY = "claude:quota_exceeded"
_QUOTA_TTL = 7200  # 2시간

_client = None
_MODEL = "claude-haiku-4-5-20251001"


def _get_client():
    """싱글톤 Anthropic 클라이언트."""
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def is_quota_exceeded() -> bool:
    """quota 초과 캐시 확인."""
    return get_cached(_QUOTA_CACHE_KEY) is not None


def call_haiku(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 200,
    temperature: float = 0.1,
) -> Optional[str]:
    """Claude Haiku 호출. 실패 시 None 반환.

    system prompt가 있으면 cache_control 자동 적용 (prompt caching).
    """
    if is_quota_exceeded():
        log.debug("claude quota 초과 캐시 활성 — 스킵")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY 없음")
        return None

    try:
        client = _get_client()

        kwargs = {
            "model": _MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        msg = client.messages.create(**kwargs)
        return (msg.content[0].text or "").strip() if msg.content else None

    except Exception as exc:
        err = str(exc)
        log.warning("claude haiku 호출 실패: %s", err)
        if "rate_limit" in err or "overloaded" in err or "insufficient" in err:
            set_cached(_QUOTA_CACHE_KEY, True, ttl=_QUOTA_TTL)
        return None
