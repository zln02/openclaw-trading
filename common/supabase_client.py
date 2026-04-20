"""Supabase 클라이언트 싱글턴 + 자동 재연결."""
import os
import time
from typing import Any, Callable

from common.logger import get_logger

_log = get_logger("supabase_client")
_client = None


def _create_client():
    """Supabase 클라이언트 생성 (내부 헬퍼)."""
    # Ensure env is loaded in any entrypoint (cron/CLI/tests)
    try:
        from common.env_loader import load_env
        load_env()
    except Exception:
        pass

    url = os.environ.get("SUPABASE_URL", "")
    # Supabase 새 secret key 포맷(sb_secret_…) 및 구 JWT(eyJ…) 양쪽 지원.
    # SUPABASE_SECRET_KEY를 우선, 없으면 SUPABASE_KEY로 폴백.
    key = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None

    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        _log.error(
            "Supabase 클라이언트 초기화 실패 — 비활성화 후 계속 실행.",
            error=str(exc)[:200],
        )
        return None


def get_supabase():
    """Supabase 클라이언트를 반환 (지연 초기화, 싱글턴)."""
    global _client
    if _client is not None:
        return _client
    _client = _create_client()
    return _client


def _reset_client():
    """기존 클라이언트 폐기 후 재생성."""
    global _client
    _client = None
    _client = _create_client()
    return _client


def run_query_with_retry(
    query_fn: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    default: Any = None,
) -> Any:
    """Supabase 쿼리를 재시도 + 자동 재연결 래퍼로 실행.

    Args:
        query_fn: supabase 클라이언트를 인자로 받아 쿼리를 실행하는 콜백.
                  예: lambda sb: sb.table("x").select("*").execute()
        max_attempts: 최대 시도 횟수.
        base_delay: 초기 대기 시간(초).
        default: 모든 시도 실패 시 반환값.
    """
    delay = base_delay
    for attempt in range(1, max_attempts + 1):
        sb = get_supabase()
        if sb is None:
            _log.warning("Supabase 클라이언트 없음 (환경변수 미설정)")
            return default
        try:
            return query_fn(sb)
        except Exception as exc:
            _log.warning(
                "Supabase 쿼리 실패",
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(exc)[:200],
            )
            if attempt == max_attempts:
                _log.error("Supabase 쿼리 최종 실패, 재연결 시도 후 포기", error=str(exc)[:200])
                return default
            # 연결 관련 오류 시 클라이언트 재생성
            _reset_client()
            time.sleep(min(delay, 10.0))
            delay *= 2.0
