"""
AI 비서 에이전트: Gmail/Notion/자율학습 등 도구를 TOOLS 리스트로 등록.
.env에서 NOTION_TOKEN, NOTION_PAGE_ID, BRAVE_API_KEY, TELEGRAM_* 등 로드.
"""
import os
import json
from pathlib import Path
from typing import Any, Callable

# .env 로드 (python-dotenv 사용 시)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# Gmail 연동 (gog 또는 동일 스타일)은 외부 CLI/API 호출로 가정.
# Notion 스킬은 로컬 함수로 등록.
from core.notion_skill import create_notion_note, update_notion_todo, query_notion_database
from core.agency_memory import search_learned, apply_pending_to_learned


def create_notion_note_tool(title: str, content: str = "", parent_page_id: str = "") -> dict[str, Any]:
    """노션에 노트(페이지) 생성. parent_page_id 없으면 .env의 NOTION_PAGE_ID 사용."""
    try:
        pid = parent_page_id.strip() or None
        return create_notion_note(title=title, content=content, parent_page_id=pid)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_notion_todo_tool(
    title: str = "",
    done: bool | None = None,
    page_id: str = "",
    database_id: str = "",
) -> dict[str, Any]:
    """노션 할 일 DB에 추가 또는 기존 항목 완료 처리. page_id 있으면 해당 페이지 업데이트."""
    try:
        pid = page_id.strip() or None
        dbid = database_id.strip() or None
        t = title.strip() or None
        return update_notion_todo(page_id=pid, database_id=dbid, title=t, done=done)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def query_notion_todo_tool(done_only: bool | None = None, database_id: str = "") -> dict[str, Any]:
    """노션 할 일 DB 조회. done_only True=완료만, False=미완료만, None=전체."""
    try:
        dbid = database_id.strip() or None
        return query_notion_database(database_id=dbid, filter_done=done_only)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def memory_search_learned_tool(keyword: str = "", limit: int = 10) -> dict[str, Any]:
    """자율 학습으로 저장된 내용 조회. keyword로 검색, 없으면 최신 목록."""
    try:
        items = search_learned(keyword=keyword, limit=limit)
        return {"ok": True, "items": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def apply_learning_approval_tool(pending_id: str = "") -> dict[str, Any]:
    """[자율 학습 제안]에 대해 사용자가 승인했을 때 호출. pending_id 없으면 최신 1건을 학습 DB에 반영."""
    try:
        pid = int(pending_id.strip()) if pending_id and pending_id.strip().isdigit() else None
        return apply_pending_to_learned(pending_id=pid)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Gmail 스타일과 동일하게 TOOLS 리스트: 이름 -> (설명, 함수)
TOOLS: list[tuple[str, str, Callable[..., dict[str, Any]]]] = [
    ("create_notion_note", "노션에 노트(페이지) 생성. title, content(선택), parent_page_id(선택).", create_notion_note_tool),
    ("update_notion_todo", "노션 할 일 추가 또는 완료 처리. title, done(True/False), page_id(업데이트 시), database_id(추가 시).", update_notion_todo_tool),
    ("query_notion_todo", "노션 할 일 목록 조회. done_only(True/False/None), database_id(선택).", query_notion_todo_tool),
    ("memory_search_learned", "자율 학습으로 저장된 내용 검색. keyword(선택), limit(기본 10).", memory_search_learned_tool),
    ("apply_learning_approval", "자율 학습 제안 승인 시 호출. pending_id 없으면 최신 1건 반영.", apply_learning_approval_tool),
]


def run_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """TOOLS에서 이름으로 찾아 실행."""
    for tool_name, _, fn in TOOLS:
        if tool_name == name:
            return fn(**kwargs)
    return {"ok": False, "error": f"Unknown tool: {name}"}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Tools:", [t[0] for t in TOOLS])
        sys.exit(0)
    name = sys.argv[1]
    kwargs = {}
    for i in range(2, len(sys.argv), 2):
        if i + 1 < len(sys.argv) and sys.argv[i].startswith("--"):
            key = sys.argv[i].lstrip("-").replace("-", "_")
            kwargs[key] = sys.argv[i + 1]
    result = run_tool(name, **kwargs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
