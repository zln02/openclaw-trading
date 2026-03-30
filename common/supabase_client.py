"""Supabase client helpers with lazy, failure-tolerant initialization."""
from __future__ import annotations

import os
import time
from typing import Any

from common.logger import get_logger

try:
    from tenacity import retry, reraise, stop_after_attempt, wait_exponential
except Exception:  # pragma: no cover - optional dependency fallback
    def retry(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def stop_after_attempt(*args, **kwargs):
        return None

    def wait_exponential(*args, **kwargs):
        return None

log = get_logger("supabase_client")

_client = None
_last_connect_attempt = 0.0

# 재연결 트리거 키워드 (httpcore 연결 끊김 에러)
_RECONNECT_ERRORS = (
    "Server disconnected",
    "RemoteProtocolError",
    "ConnectionError",
    "Connection reset",
    "Connection reset by peer",
    "ConnectionTerminated",
    "BrokenResourceError",
    "ReadError",
)


def create_supabase_client(url: str, key: str) -> Any | None:
    """Create a Supabase client without propagating SDK import/init failures."""
    if not url or not key:
        return None

    try:
        from supabase import create_client
    except Exception:
        return None

    try:
        return create_client(url, key)
    except Exception:
        return None


def create_supabase_client_from_env() -> object | None:
    """Create a Supabase client from env, accepting both secret-role key names."""
    try:
        from common.env_loader import load_env

        load_env()
    except Exception:
        pass

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get("SUPABASE_KEY", "")
    return create_supabase_client(url, key)


def reset_client() -> None:
    """싱글턴 클라이언트를 초기화하여 다음 호출 시 재연결하게 한다."""
    global _client
    _client = None


def _reset_client() -> None:
    """Backward-compatible reset alias."""
    reset_client()


def get_supabase() -> Any:
    """Supabase 클라이언트를 반환 (지연 초기화, 자동 재연결)."""
    global _client, _last_connect_attempt
    if _client is not None:
        return _client

    # Ensure env is loaded in any entrypoint (cron/CLI/tests)
    try:
        from common.env_loader import load_env

        load_env()
    except Exception:
        pass

    now = time.time()
    if now - _last_connect_attempt < 30:
        return None

    _last_connect_attempt = now
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        log.warning("Supabase URL/KEY 미설정")
        return None

    for attempt in range(3):
        try:
            _client = create_supabase_client(url, key)
            if _client is None:
                raise RuntimeError("Supabase client unavailable")
            log.info("Supabase 연결 성공")
            return _client
        except Exception as exc:
            log.warning(f"Supabase 연결 시도 {attempt + 1}/3 실패: {exc}")
            if attempt < 2:
                time.sleep(2)

    return None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def run_query_with_retry(query_fn) -> Any:
    """Execute a Supabase query with retry/backoff.
    연결 끊김 에러 발생 시 싱글턴을 리셋하여 재연결 후 재시도한다.
    """
    supabase = get_supabase()
    if not supabase:
        raise RuntimeError("Supabase client unavailable")
    try:
        return query_fn(supabase)
    except Exception as exc:
        # 연결 끊김 에러면 싱글턴 리셋 → tenacity가 재시도 시 새 클라이언트 생성
        if any(kw in str(exc) for kw in _RECONNECT_ERRORS):
            reset_client()
        raise


def run_table_query(table: str, query_fn) -> Any:
    """Convenience wrapper for table-scoped retryable queries."""
    return run_query_with_retry(lambda supabase: query_fn(supabase.table(table)))
