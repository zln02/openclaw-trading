"""Supabase 클라이언트 싱글턴."""
import os
from typing import Optional

_client = None


def get_supabase():
    """Supabase 클라이언트를 반환 (지연 초기화, 싱글턴)."""
    global _client
    if _client is not None:
        return _client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        return None

    from supabase import create_client
    _client = create_client(url, key)
    return _client
