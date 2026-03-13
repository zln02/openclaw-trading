"""Supabase client helpers with lazy, failure-tolerant initialization."""
from __future__ import annotations

import os

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

_client = None


def create_supabase_client(url: str, key: str):
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


def get_supabase():
    """Supabase 클라이언트를 반환 (지연 초기화, 싱글턴)."""
    global _client
    if _client is not None:
        return _client

    # Ensure env is loaded in any entrypoint (cron/CLI/tests)
    try:
        from common.env_loader import load_env

        load_env()
    except Exception:
        pass

    _client = create_supabase_client_from_env()
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def run_query_with_retry(query_fn):
    """Execute a Supabase query with retry/backoff."""
    supabase = get_supabase()
    if not supabase:
        raise RuntimeError("Supabase client unavailable")
    return query_fn(supabase)


def run_table_query(table: str, query_fn):
    """Convenience wrapper for table-scoped retryable queries."""
    return run_query_with_retry(lambda supabase: query_fn(supabase.table(table)))
