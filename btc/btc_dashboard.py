#!/usr/bin/env python3
"""
OpenClaw Trading Dashboard — FastAPI entry point
Port: 8080

All API routes are split into:
  - btc/routes/btc_api.py   (BTC endpoints)
  - btc/routes/stock_api.py (Korean stock endpoints)
  - btc/routes/us_api.py    (US stock endpoints)
"""

import os
import secrets
import sys
import time
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.config import DASHBOARD_PORT

load_env()

app = FastAPI(title="OpenClaw Trading Dashboard")

# ── Basic Auth ──────────────────────────────────────────────────────────────
_security = HTTPBasic(auto_error=False)
_DASH_USER = os.environ.get("DASHBOARD_USER", "openclaw")
_DASH_PASS = os.environ.get("DASHBOARD_PASSWORD", "")

# 인증 실패 rate limiting: IP당 5분 내 5회 실패 시 잠금
_AUTH_FAIL: dict = defaultdict(list)
_AUTH_LOCKOUT_SEC = 300   # 5분
_AUTH_MAX_FAILS = 5


def _require_auth(request: Request, credentials: HTTPBasicCredentials = Depends(_security)):
    """HTTP Basic Auth — DASHBOARD_PASSWORD 미설정 시 서버 시작 경고 후 거부."""
    client_ip = request.client.host if request.client else "unknown"

    # 비밀번호 미설정이면 모든 요청 거부 (개발 편의 우선순위보다 보안 우선)
    if not _DASH_PASS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DASHBOARD_PASSWORD 환경변수를 설정하세요.",
        )

    # Rate limiting: 잠긴 IP 차단
    now = time.time()
    recent = [t for t in _AUTH_FAIL[client_ip] if now - t < _AUTH_LOCKOUT_SEC]
    _AUTH_FAIL[client_ip] = recent
    if len(recent) >= _AUTH_MAX_FAILS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic realm='OpenClaw Dashboard'"},
        )

    ok_user = secrets.compare_digest(credentials.username.encode(), _DASH_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), _DASH_PASS.encode())
    if not (ok_user and ok_pass):
        _AUTH_FAIL[client_ip].append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic realm='OpenClaw Dashboard'"},
        )

_CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "https://opentrading.duckdns.org,http://localhost:3000,https://localhost:3000,http://127.0.0.1:3000,https://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

from btc.routes.btc_api import router as btc_router
from btc.routes.stock_api import router as stock_router
from btc.routes.us_api import router as us_router

app.include_router(btc_router,   dependencies=[Depends(_require_auth)])
app.include_router(stock_router, dependencies=[Depends(_require_auth)])
app.include_router(us_router,    dependencies=[Depends(_require_auth)])


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    """헬스 체크 — 인증 불필요."""
    try:
        from common.health import health_monitor

        payload = await health_monitor.run_checks()
        payload["service"] = "openclaw-dashboard"
        return payload
    except Exception as exc:
        return {
            "status": "degraded",
            "service": "openclaw-dashboard",
            "components": {},
            "error": str(exc),
        }


# Serve built React dashboard (production)
_DIST = Path(__file__).resolve().parents[1] / "dashboard" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", dependencies=[Depends(_require_auth)])
    async def spa_fallback(full_path: str):
        """SPA fallback — serve index.html for non-API routes only."""
        if full_path.startswith("api/"):
            return Response(status_code=404, content="API endpoint not found")

        # Path traversal 방지: 경로 정규화 후 _DIST 내부인지 검증
        try:
            resolved = (_DIST / full_path).resolve()
            resolved.relative_to(_DIST.resolve())  # _DIST 외부면 ValueError
        except (ValueError, Exception):
            return Response(status_code=400, content="Invalid path")

        # 정적 파일 확장자는 StaticFiles가 처리해야 하므로 여기선 404
        static_extensions = {"js", "css", "png", "jpg", "jpeg", "gif", "svg", "ico", "woff", "woff2", "map"}
        if "." in full_path:
            ext = full_path.rsplit(".", 1)[-1].lower()
            if ext in static_extensions:
                return Response(status_code=404, content="Static file not found")

        index = _DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return Response(status_code=404, content="Index file not found")


if __name__ == "__main__":
    ssl_certfile = os.environ.get("SSL_CERTFILE")
    ssl_keyfile = os.environ.get("SSL_KEYFILE")

    uvicorn_kwargs = {
        "app": app,
        "host": "0.0.0.0",
        "port": DASHBOARD_PORT,
    }
    if ssl_certfile and ssl_keyfile:
        uvicorn_kwargs["ssl_certfile"] = ssl_certfile
        uvicorn_kwargs["ssl_keyfile"] = ssl_keyfile
    elif ssl_certfile or ssl_keyfile:
        print("SSL_CERTFILE and SSL_KEYFILE must both be set. Starting without HTTPS.", file=sys.stderr)

    uvicorn.run(**uvicorn_kwargs)
