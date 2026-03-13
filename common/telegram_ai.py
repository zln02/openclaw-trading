"""Telegram AI responder using Claude API."""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

from common.env_loader import load_env

try:
    import anthropic
except Exception:  # pragma: no cover - optional dependency fallback
    anthropic = None


_client = None
_chat_histories: dict[str, list[dict[str, str]]] = defaultdict(list)


def _trim_reply(text: str, limit: int = 500) -> str:
    clean = str(text).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def _format_context(market_context: Any) -> str:
    if isinstance(market_context, str):
        return market_context
    if not isinstance(market_context, dict):
        return str(market_context or "")

    lines: list[str] = []
    for key, value in market_context.items():
        label = str(key).replace("_", " ")
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def get_client():
    global _client
    if _client is not None:
        return _client

    load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic or not api_key:
        return None

    _client = anthropic.Anthropic(api_key=api_key)
    return _client


async def ai_respond(user_id: int | str, message: str, market_context: Any) -> str:
    """Generate an AI response with the latest system context."""

    client = get_client()
    if client is None:
        return "⚠️ AI 응답을 사용할 수 없습니다. ANTHROPIC_API_KEY 설정을 확인하세요."

    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    history = _chat_histories[str(user_id)]
    history.append({"role": "user", "content": message})
    if len(history) > 20:
        history[:] = history[-20:]

    context_text = _format_context(market_context)
    system_prompt = (
        "너는 OpenClaw Trading System의 AI 트레이딩 어시스턴트다.\n"
        "실시간 시스템 데이터를 기반으로 정확하고 간결하게 답변한다.\n"
        "한국어로 500자 이내로 답한다.\n"
        "매매 실행은 직접 하지 말고 /stop, /resume, /sell_all 명령어를 안내한다.\n"
        "모르는 내용은 모른다고 말한다.\n\n"
        f"{context_text}"
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=history,
        )
        reply = _trim_reply(response.content[0].text)
        history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as exc:
        return f"⚠️ AI 응답 오류: {str(exc)[:120]}"
