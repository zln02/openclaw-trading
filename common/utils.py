"""Shared utility functions for the OpenClaw trading system."""
import json
import os
import tempfile
from datetime import date, datetime
from typing import Any, Optional


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
        return json.loads(text[s : e + 1])
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


def parse_day(value: Optional[Any] = None) -> date:
    """str/date/datetime/None → date 객체 변환."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return datetime.now().date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
