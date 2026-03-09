"""API 응답 표준화 헬퍼 — OpenClaw Trading System."""
from __future__ import annotations

from fastapi.responses import JSONResponse


def api_error(message: str, status_code: int = 500, detail: str | None = None) -> JSONResponse:
    """표준 에러 응답."""
    body: dict = {"error": True, "message": message}
    if detail:
        body["detail"] = detail
    return JSONResponse(content=body, status_code=status_code)


def api_success(data, message: str = "ok") -> dict:
    """표준 성공 응답."""
    return {"error": False, "message": message, "data": data}
