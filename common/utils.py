"""Shared utility functions for the OpenClaw trading system."""
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
from typing import Any, Optional


def utc_now() -> datetime:
    """현재 UTC 시각 반환 (timezone-aware)."""
    return datetime.now(timezone.utc)


def safe_float(value: Any, default: float = 0.0) -> float:
    """값을 float으로 안전하게 변환. 변환 실패 시 default 반환."""
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def parse_json_from_text(raw: str) -> dict:
    """LLM 응답에서 JSON 블록 파싱. ```json 마커, 앞뒤 텍스트 제거."""
    text = (raw or "").strip().replace("```json", "").replace("```", "").strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    s = text.find("{")
    e = text.rfind("}")
    if s >= 0 and e > s:
        return json.loads(text[s : e + 1])  # noqa: E203
    raise ValueError("JSON object not found")


def to_iso_day(value: Any) -> str:
    """str/date/datetime → 'YYYY-MM-DD' 문자열 변환."""
    return str(value or "")[:10]


def atomic_write_json(path: str, data: dict, *, ensure_ascii: bool = False) -> None:
    """원자적 JSON 파일 쓰기 (temp → rename).

    경쟁 조건 없이 안전하게 JSON 파일을 갱신한다.
    실패 시 기존 파일이 손상되지 않음.

    Args:
        path: 대상 파일 경로 (str 또는 Path)
        data: 저장할 dict
        ensure_ascii: JSON 인코딩 옵션
    """
    path = str(path)
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=2)
        os.replace(tmp_path, path)  # 원자적 교체 (POSIX 보장)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def generate_order_id(market: str, symbol: str, side: str, extra: str = "") -> str:
    """거래 멱등성 키 생성.

    형식: {market}_{symbol}_{side}_{minute_timestamp}_{hash4}
    같은 분(minute) 내 동일 심볼+방향 주문은 동일한 order_id를 반환하여
    네트워크 재시도 시 중복 주문을 방지한다.

    Args:
        market: 'btc', 'kr', 'us'
        symbol: 종목코드/심볼
        side: 'buy' or 'sell'
        extra: 추가 구분 키 (예: split_stage)
    """
    now = datetime.now(timezone.utc)
    minute_ts = now.strftime("%Y%m%d%H%M")
    raw = f"{market}_{symbol}_{side}_{minute_ts}_{extra}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"{market}_{symbol}_{side}_{minute_ts}_{short_hash}"


def check_order_idempotency(supabase_client, table: str, order_id: str) -> bool:
    """Supabase에서 동일 order_id가 이미 존재하는지 확인.

    Returns:
        True if duplicate exists (should skip), False if safe to proceed.
    """
    if not supabase_client or not order_id:
        return False
    try:
        result = supabase_client.table(table).select("id").eq("order_id", order_id).limit(1).execute()
        return bool(result.data)
    except Exception:
        # order_id 컬럼이 없는 경우 등 — 안전하게 진행 허용
        return False


def parse_day(value: Optional[Any] = None) -> date:
    """str/date/datetime/None → date 객체 변환."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return datetime.now().date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
