"""
자율 학습용 SQLite DB (agency_memory.db).
학습 승인된 내용(learned_content)과 승인 대기(pending_approvals) 관리.
"""
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

# DB 경로: secretary 프로젝트 루트 또는 환경변수
def _db_path() -> Path:
    p = os.getenv("AGENCY_MEMORY_DB")
    if p:
        return Path(p)
    return Path(__file__).resolve().parent.parent / "agency_memory.db"


def get_connection() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS learned_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                content TEXT,
                query TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS pending_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                summary TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_learned_created ON learned_content(created_at);
        """)
        conn.commit()
    finally:
        if close:
            conn.close()


def add_pending(query: str, summary: str, content: str, sources: Optional[list[dict]] = None) -> int:
    conn = get_connection()
    try:
        init_db(conn)
        cur = conn.execute(
            "INSERT INTO pending_approvals (query, summary, content, sources_json) VALUES (?, ?, ?, ?)",
            (query, summary, content, json.dumps(sources or [], ensure_ascii=False) if sources else None),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_latest_pending() -> Optional[dict[str, Any]]:
    conn = get_connection()
    try:
        init_db(conn)
        row = conn.execute(
            "SELECT id, query, summary, content, sources_json, created_at FROM pending_approvals ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("sources_json"):
            d["sources"] = json.loads(d["sources_json"])
        return d
    finally:
        conn.close()


def apply_pending_to_learned(pending_id: Optional[int] = None) -> dict[str, Any]:
    """대기 중인 항목을 학습 DB로 이동. pending_id 없으면 최신 1건."""
    conn = get_connection()
    try:
        init_db(conn)
        if pending_id is None:
            row = conn.execute("SELECT id, query, summary, content, sources_json FROM pending_approvals ORDER BY id DESC LIMIT 1").fetchone()
        else:
            row = conn.execute("SELECT id, query, summary, content, sources_json FROM pending_approvals WHERE id = ?", (pending_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "승인 대기 항목이 없습니다."}
        pid, query, summary, content, sources_json = row
        sources = json.loads(sources_json) if sources_json else []
        source_url = sources[0].get("url", "") if sources else ""
        title = sources[0].get("title", summary[:100]) if sources else summary[:100]
        conn.execute(
            "INSERT INTO learned_content (source_url, title, summary, content, query) VALUES (?, ?, ?, ?, ?)",
            (source_url, title, summary, content, query),
        )
        conn.execute("DELETE FROM pending_approvals WHERE id = ?", (pid,))
        conn.commit()
        return {"ok": True, "pending_id": pid, "message": "학습 내용에 반영했습니다."}
    finally:
        conn.close()


def add_learned(source_url: str, title: str, summary: str, content: str = "", query: str = "") -> int:
    conn = get_connection()
    try:
        init_db(conn)
        cur = conn.execute(
            "INSERT INTO learned_content (source_url, title, summary, content, query) VALUES (?, ?, ?, ?, ?)",
            (source_url, title, summary, content, query),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def search_learned(keyword: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """대화에서 참고할 학습 내용 조회. keyword 없으면 최신순."""
    conn = get_connection()
    try:
        init_db(conn)
        if keyword and keyword.strip():
            rows = conn.execute(
                "SELECT id, source_url, title, summary, content, query, created_at FROM learned_content "
                "WHERE title LIKE ? OR summary LIKE ? OR content LIKE ? OR query LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{keyword.strip()}%", f"%{keyword.strip()}%", f"%{keyword.strip()}%", f"%{keyword.strip()}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, source_url, title, summary, content, query, created_at FROM learned_content ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
