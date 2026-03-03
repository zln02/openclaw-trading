"""Shared utility functions for the OpenClaw trading system."""
import json
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


def parse_day(value: Optional[Any] = None) -> date:
    """str/date/datetime/None → date 객체 변환."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return datetime.now().date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
