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
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status
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
_security = HTTPBasic()
_DASH_USER = os.environ.get("DASHBOARD_USER", "openclaw")
_DASH_PASS = os.environ.get("DASHBOARD_PASSWORD", "")


def _require_auth(credentials: HTTPBasicCredentials = Depends(_security)):
    """환경변수에 DASHBOARD_PASSWORD가 설정된 경우에만 인증 적용."""
    if not _DASH_PASS:
        return  # 비번 미설정 시 인증 생략 (개발 편의)
    ok_user = secrets.compare_digest(credentials.username.encode(), _DASH_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), _DASH_PASS.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic realm='OpenClaw Dashboard'"},
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    import time
    return {"status": "ok", "service": "openclaw-dashboard", "uptime_placeholder": int(time.time())}


# Serve built React dashboard (production)
_DIST = Path(__file__).resolve().parents[1] / "dashboard" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", dependencies=[Depends(_require_auth)])
    async def spa_fallback(full_path: str):
        """SPA fallback — serve index.html for non-API routes only."""
        if full_path.startswith("api/"):
            return Response(status_code=404, content="API endpoint not found")
        static_extensions = ["js", "css", "png", "jpg", "jpeg", "gif", "svg", "ico", "woff", "woff2"]
        if "." in full_path:
            ext = full_path.split(".")[-1].lower()
            if ext in static_extensions:
                return Response(status_code=404, content="Static file not found")
        index = _DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return Response(status_code=404, content="Index file not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_PORT)
