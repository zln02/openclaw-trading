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

# audit fix: /metrics 인증 추가 — expose()/mount() 대신 직접 라우트 등록
# Instrumentator는 instrument()만 호출(계측), expose()는 생략 (직접 라우트에서 응답)
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app)  # expose 하지 않음 — 아래 /metrics 라우트에서 처리
    _PROM_INSTRUMENTATOR = True
except ImportError:
    _PROM_INSTRUMENTATOR = False

_PROM_CLIENT_AVAILABLE = False
try:
    from prometheus_client import generate_latest as _prom_generate_latest, CONTENT_TYPE_LATEST as _PROM_CONTENT_TYPE
    _PROM_CLIENT_AVAILABLE = True
except ImportError:
    pass

# Register custom trading metrics (counters/gauges populated by agents)
try:
    import common.prometheus_metrics  # noqa: F401 — registers metric objects
except ImportError:
    pass

# ── Basic Auth ──────────────────────────────────────────────────────────────
_security = HTTPBasic(auto_error=False)
_DASH_USER = os.environ.get("DASHBOARD_USER", "openclaw")


def _load_dashboard_password() -> str:
    env_password = os.environ.get("DASHBOARD_PASSWORD", "").strip()
    if env_password:
        return env_password

    secret_paths = [
        Path("/run/secrets/openclaw/DASHBOARD_PASSWORD"),
        Path(__file__).resolve().parents[1] / ".docker-secrets" / "DASHBOARD_PASSWORD",
    ]
    for path in secret_paths:
        try:
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return ""


_DASH_PASS = _load_dashboard_password()

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

_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key"],
)

from btc.routes.btc_api import router as btc_router
from btc.routes.stock_api import router as stock_router
from btc.routes.us_api import router as us_router
from api.signal_api import router as public_signal_router
from api.ws_stream import router as public_ws_router
from api.webhook_manager import router as public_webhook_router
from api.push_notifier import router as public_push_router

app.include_router(btc_router,   dependencies=[Depends(_require_auth)])
app.include_router(stock_router, dependencies=[Depends(_require_auth)])
app.include_router(us_router,    dependencies=[Depends(_require_auth)])
app.include_router(public_signal_router)
app.include_router(public_ws_router)
app.include_router(public_webhook_router)
app.include_router(public_push_router)


# audit fix: /metrics 인증 추가 — 거래 데이터 노출 방지
@app.get("/metrics", include_in_schema=False, dependencies=[Depends(_require_auth)])
async def metrics_endpoint():
    """Prometheus 메트릭 — Basic Auth 필수."""
    if not _PROM_CLIENT_AVAILABLE:
        return Response(status_code=503, content="prometheus_client not installed")
    data = _prom_generate_latest()
    return Response(content=data, media_type=_PROM_CONTENT_TYPE)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    """간단 헬스 체크 — 인증 불필요."""
    import time
    return {"status": "ok", "service": "openclaw-dashboard", "uptime_placeholder": int(time.time())}


@app.get("/api/health", dependencies=[Depends(_require_auth)])
async def health_detailed():
    """상세 헬스 체크 (Upbit/Supabase/Kiwoom/Cron 상태) — P2: Basic Auth 필수."""
    from common.health import health_monitor
    return await health_monitor.run_checks()


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
    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_PORT)
