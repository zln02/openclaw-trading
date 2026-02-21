"""
Notion 스킬: notion-client를 사용한 페이지 생성 및 DB 조회.
.env의 NOTION_TOKEN, NOTION_PAGE_ID 사용.
"""
import os
import re
from typing import Any, Optional

from notion_client import Client


def _normalize_id(raw: str) -> str:
    """하이픈·공백·비hex 문자 제거 후 32자리 ID 반환."""
    return re.sub(r"[^0-9a-f]", "", (raw or "").strip().lower())


def _get_client() -> Client:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise ValueError("NOTION_TOKEN이 .env에 설정되지 않았습니다.")
    return Client(auth=token, notion_version="2022-06-28")


def _get_page_id() -> str:
    page_id = os.getenv("NOTION_PAGE_ID")
    if not page_id:
        raise ValueError("NOTION_PAGE_ID가 .env에 설정되지 않았습니다.")
    return _normalize_id(page_id)


def _resolve_to_database_id(client: Client, raw_id: str) -> str:
    """ID가 페이지면 해당 페이지 내 첫 번째 child_database ID를 반환."""
    nid = _normalize_id(raw_id)
    try:
        client.databases.retrieve(database_id=nid)
        return nid
    except Exception as e:
        if "page, not a database" not in str(e):
            raise
    blocks = client.blocks.children.list(block_id=nid)
    for b in blocks.get("results", []):
        if b.get("type") == "child_database":
            return _normalize_id(b["id"])
    raise ValueError("해당 페이지에서 데이터베이스를 찾을 수 없습니다.")


def create_notion_note(title: str, content: str = "", parent_page_id: Optional[str] = None) -> dict[str, Any]:
    client = _get_client()
    parent_id = _normalize_id(parent_page_id or os.getenv("NOTION_PAGE_ID") or "")
    if not parent_id:
        raise ValueError("NOTION_PAGE_ID가 .env에 설정되지 않았습니다.")
    body = {"parent": {"page_id": parent_id}, "properties": {"title": {"title": [{"type": "text", "text": {"content": title[:2000]}}]}}}
    page = client.pages.create(**body)
    if content:
        client.blocks.children.append(block_id=page["id"], children=[{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]}}])
    return {"ok": True, "page_id": page["id"], "url": page.get("url", ""), "title": title}


def update_notion_todo(database_id: Optional[str] = None, page_id: Optional[str] = None, title: Optional[str] = None, done: Optional[bool] = None) -> dict[str, Any]:
    client = _get_client()
    raw_id = database_id or page_id or os.getenv("NOTION_PAGE_ID") or ""
    target_id = _normalize_id(raw_id)
    if not target_id:
        raise ValueError("NOTION_PAGE_ID 또는 database_id/page_id가 필요합니다.")
    if page_id:
        props = {}
        if done is not None: props["Done"] = {"checkbox": done}
        if title is not None: props["Name"] = {"title": [{"type": "text", "text": {"content": title[:2000]}}]}
        if not props: return {"ok": False, "error": "업데이트할 속성(title 또는 done)을 지정하세요."}
        client.pages.update(page_id=target_id, properties=props)
        return {"ok": True, "page_id": target_id, "updated": list(props.keys())}
    db_id = _resolve_to_database_id(client, raw_id)
    props = {"Name": {"title": [{"type": "text", "text": {"content": (title or "할 일")[:2000]}}]}, "Done": {"checkbox": done if done is not None else False}}
    page = client.pages.create(parent={"database_id": db_id}, properties=props)
    return {"ok": True, "page_id": page["id"], "url": page.get("url", ""), "title": title or "할 일"}


def query_notion_database(database_id: Optional[str] = None, filter_done: Optional[bool] = None, page_size: int = 50) -> dict[str, Any]:
    client = _get_client()
    db_id = _resolve_to_database_id(client, database_id or _get_page_id())
    body = {"page_size": page_size}
    if filter_done is not None: body["filter"] = {"property": "Done", "checkbox": {"equals": filter_done}}
    resp = client.request(path=f"databases/{db_id}/query", method="POST", body=body)
    items = []
    for r in resp.get("results", []):
        props = r.get("properties", {})
        name = props.get("Name", {}).get("title", [{}])
        title = (name[0].get("plain_text", "") or "").strip() if name else ""
        items.append({"id": r["id"], "title": title, "done": props.get("Done", {}).get("checkbox", False), "url": r.get("url", "")})
    return {"ok": True, "items": items}
