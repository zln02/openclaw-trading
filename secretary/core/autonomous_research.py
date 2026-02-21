"""
자율 학습: 1시간마다 관심 주제를 Brave Search로 검색하고,
새로운 내용이 있으면 Telegram으로 '[자율 학습 제안]' 알림 후 pending_approvals에 저장.
"""
import json
import os
import re
from pathlib import Path
from typing import Any

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import requests

from .agency_memory import add_pending, get_connection, init_db, search_learned

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _get_interests() -> list[str]:
    raw = os.getenv("RESEARCH_INTERESTS", "엔비디아 주가, 최신 AI 트렌드")
    raw = raw.strip()
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return [s.strip() for s in re.split(r"[,，]", raw) if s.strip()]


def _brave_search(query: str, api_key: str, count: int = 5) -> list[dict[str, Any]]:
    if not api_key:
        return []
    try:
        r = requests.get(
            BRAVE_API_URL,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": count},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("web", {}).get("results", []) or []
    except Exception:
        return []


def _send_telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id.strip(), "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


def _make_summary(results: list[dict], query: str) -> tuple[str, str]:
    """(요약 텍스트, 본문 텍스트) 반환."""
    lines = [f"[검색: {query}]"]
    body_parts = []
    for i, hit in enumerate(results[:5], 1):
        title = hit.get("title") or ""
        desc = hit.get("description") or ""
        url = hit.get("url") or ""
        line = f"{i}. {title}\n   {desc[:200]}{'…' if len(desc) > 200 else ''}"
        if url:
            line += f"\n   {url}"
        lines.append(line)
        body_parts.append({"title": title, "description": desc, "url": url})
    summary = "\n".join(lines)
    content = json.dumps({"query": query, "results": body_parts}, ensure_ascii=False, indent=2)
    return summary, content


def autonomous_research() -> dict[str, Any]:
    """
    1시간마다 호출: 관심사 검색 → 새로울 경우 pending 추가 + 텔레그램 알림.
    """
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return {"ok": False, "error": "BRAVE_API_KEY가 설정되지 않았습니다."}

    interests = _get_interests()
    if not interests:
        return {"ok": True, "message": "RESEARCH_INTERESTS가 비어 있습니다.", "notified": False}

    all_results = []
    all_sources = []
    for q in interests:
        results = _brave_search(q, api_key)
        for r in results:
            all_results.append((q, r))
            all_sources.append({"title": r.get("title"), "description": r.get("description"), "url": r.get("url")})

    if not all_results:
        return {"ok": True, "message": "검색 결과 없음", "notified": False}

    # 요약/본문 생성 (여러 관심사 합침)
    query_label = ", ".join(interests)
    summary_parts = []
    content_parts = []
    for q, hit in all_results[:10]:
        title = hit.get("title") or ""
        desc = hit.get("description") or ""
        summary_parts.append(f"• [{q}] {title}: {desc[:150]}…" if len(desc) > 150 else f"• [{q}] {title}: {desc}")
        content_parts.append({"query": q, "title": title, "description": desc, "url": hit.get("url")})
    summary = "\n".join(summary_parts)
    content = json.dumps({"queries": interests, "items": content_parts}, ensure_ascii=False, indent=2)

    # 중복 완화: 최근 학습 DB에 비슷한 제목이 있으면 스킵 가능 (선택)
    recent = search_learned(limit=5)
    for r in recent:
        if any(hit.get("title") and (hit["title"] in r.get("title", "") or hit["title"] in r.get("summary", "")) for _, hit in all_results[:5]):
            return {"ok": True, "message": "최근 학습 내용과 유사하여 스킵", "notified": False}

    # pending 추가 후 텔레그램 알림
    pending_id = add_pending(query=query_label, summary=summary, content=content, sources=all_sources[:10])
    msg = "[자율 학습 제안] 새로운 정보를 찾았습니다. 학습할까요?\n(승인하려면 '학습해줘' 또는 '승인' 이라고 답장하세요)"
    sent = _send_telegram(msg)
    return {"ok": True, "pending_id": pending_id, "notified": sent, "message": "알림 발송" if sent else "Telegram 미발송(토큰/채팅ID 확인)"}
