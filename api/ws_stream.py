"""Public WebSocket signal stream (Phase E-2)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.regime_classifier import RegimeClassifier
from common.logger import get_logger

from api.signal_api import (
    _kr_top_picks,
    _load_long_short_plan,
    _us_top_picks,
    load_market_allocation,
    require_public_api_key,
)

log = get_logger("public_ws_stream")
router = APIRouter(prefix="/api/v1", tags=["public-ws"])


def _now_iso() -> str:
    return datetime.now().isoformat()


def _btc_payload() -> dict:
    try:
        from btc.routes.btc_api import _compute_composite_sync

        payload = _compute_composite_sync()
    except Exception:
        payload = {"composite": {"total": 0, "recommendation": "HOLD"}, "trend": "SIDEWAYS", "fg_value": 50}
    return {
        "composite_score": payload.get("composite", {}).get("total", 0),
        "trend": payload.get("trend", "SIDEWAYS"),
        "fg_index": payload.get("fg_value", 50),
        "recommendation": payload.get("composite", {}).get("recommendation", "HOLD"),
    }


def _kr_payload() -> dict:
    picks, updated_at = _kr_top_picks()
    return {"top_picks": picks, "updated_at": updated_at or _now_iso()}


def _us_payload() -> dict:
    picks, updated_at = _us_top_picks()
    return {"top_picks": picks, "updated_at": updated_at or _now_iso()}


def _regime_payload() -> dict:
    row = RegimeClassifier().classify()
    return {
        "current_regime": row.get("regime", "TRANSITION"),
        "confidence": row.get("confidence", 0.5),
        "factors": row.get("features", {}),
    }


def _allocation_payload() -> dict:
    alloc = load_market_allocation().get("allocation") or {}
    return {
        "btc": alloc.get("btc", 0.0),
        "kr": alloc.get("kr", 0.0),
        "us": alloc.get("us", 0.0),
        "cash": alloc.get("cash", 0.0),
    }


def _alert_payload() -> dict:
    plan = _load_long_short_plan()
    return {
        "long_count": len(plan.get("long_candidates", []) or []),
        "short_count": len(plan.get("short_candidates", []) or []),
        "regime": plan.get("regime", "UNKNOWN"),
    }


def _event(name: str, data: dict) -> dict:
    return {"type": name, "data": data, "timestamp": _now_iso()}


def _snapshot_events() -> list[dict]:
    return [
        _event("btc_signal", _btc_payload()),
        _event("kr_trade", _kr_payload()),
        _event("us_trade", _us_payload()),
        _event("regime_change", _regime_payload()),
        _event("alert", _alert_payload()),
        _event("portfolio_allocation", _allocation_payload()),
    ]


@router.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket):
    # P1: 헤더 우선 (URL 노출 방지), 쿼리 파라미터 fallback (하위 호환)
    api_key = (
        websocket.headers.get("x-api-key")
        or websocket.headers.get("authorization", "").replace("Bearer ", "")
        or str(websocket.query_params.get("api_key") or "")
    ).strip()
    try:
        require_public_api_key(websocket, x_api_key=api_key)
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    last_sent: dict[str, str] = {}
    try:
        ack = _event("connection_ack", {"status": "connected"})
        await websocket.send_json(ack)
        last_sent[ack["type"]] = json.dumps(ack, ensure_ascii=False, sort_keys=True)
        for item in _snapshot_events():
            payload = json.dumps(item, ensure_ascii=False, sort_keys=True)
            last_sent[item["type"]] = payload
            await websocket.send_json(item)

        while True:
            await asyncio.sleep(10)
            for item in _snapshot_events():
                payload = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if last_sent.get(item["type"]) == payload:
                    continue
                last_sent[item["type"]] = payload
                await websocket.send_json(item)
    except WebSocketDisconnect:
        log.info("public websocket disconnected")
    except Exception as exc:
        log.warning("public websocket failed", error=str(exc))
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
