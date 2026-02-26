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
from fastapi.responses import Response
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.env_loader import load_env
from common.config import DASHBOARD_PORT

load_env()

app = FastAPI(title="OpenClaw Trading Dashboard")

from btc.routes.btc_api import router as btc_router
from btc.routes.stock_api import router as stock_router
from btc.routes.us_api import router as us_router

app.include_router(btc_router)
app.include_router(stock_router)
app.include_router(us_router)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_PORT)
