"""Shared utility functions for the OpenClaw trading system."""
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    """값을 float으로 안전하게 변환. 변환 실패 시 default 반환."""
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default
