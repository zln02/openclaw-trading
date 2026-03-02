#!/usr/bin/env python3
"""
OpenClaw Trading Dashboard — FastAPI entry point
Port: 8080

All API routes are split into:
  - btc/routes/btc_api.py   (BTC endpoints)
  - btc/routes/stock_api.py (Korean stock endpoints)
  - btc/routes/us_api.py    (US stock endpoints)
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.config import DASHBOARD_PORT

load_env()

app = FastAPI(title="OpenClaw Trading Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from btc.routes.btc_api import router as btc_router
from btc.routes.stock_api import router as stock_router
from btc.routes.us_api import router as us_router

app.include_router(btc_router)
app.include_router(stock_router)
app.include_router(us_router)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    """헬스 체크 (로드밸런서/모니터링용)."""
    import time
    return {
        "status": "ok",
        "service": "openclaw-dashboard",
        "uptime_placeholder": int(time.time()),
    }


# Serve built React dashboard (production)
_DIST = Path(__file__).resolve().parents[1] / "dashboard" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA fallback — serve index.html for non-API routes only."""
        # API 경로는 FastAPI 라우터가 처리하므로 여기서 처리하지 않음
        # API 경로가 아닌 경우에만 SPA fallback 적용
        
        # API 경로 패턴
        if full_path.startswith("api/"):
            return Response(status_code=404, content="API endpoint not found")
        
        # 정적 파일 확장자
        static_extensions = ["js", "css", "png", "jpg", "jpeg", "gif", "svg", "ico", "woff", "woff2"]
        if "." in full_path:
            ext = full_path.split(".")[-1].lower()
            if ext in static_extensions:
                return Response(status_code=404, content="Static file not found")
        
        # SPA fallback
        index = _DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return Response(status_code=404, content="Index file not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_PORT)
