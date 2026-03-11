"""Webhook registration and delivery manager (Phase E-3)."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, Body, Depends, HTTPException

from common.api_utils import api_success
from common.config import BRAIN_PATH
from common.logger import get_logger
from common.supabase_client import get_supabase

from api.signal_api import require_public_api_key

router = APIRouter(prefix="/api/v1", tags=["public-webhooks"])
log = get_logger("webhook_manager")
supabase = get_supabase()

WEBHOOKS_PATH = BRAIN_PATH / "webhooks" / "registry.json"
DELIVERY_LOG_PATH = BRAIN_PATH / "webhooks" / "delivery_log.jsonl"
TABLE = "webhooks"
ALLOWED_EVENTS = {"btc_signal", "kr_trade", "us_trade", "regime_change", "alert", "portfolio_allocation"}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_registry() -> list[dict]:
    if not WEBHOOKS_PATH.exists():
        return []
    try:
        payload = json.loads(WEBHOOKS_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _save_registry(rows: list[dict]) -> Path:
    WEBHOOKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEBHOOKS_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return WEBHOOKS_PATH


def _append_delivery_log(row: dict) -> None:
    DELIVERY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DELIVERY_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _public_id(url: str, secret: str) -> str:
    return hashlib.sha256(f"{url}|{secret}".encode("utf-8")).hexdigest()[:16]


def _normalize_events(events: list[str]) -> list[str]:
    out = []
    for event in events or []:
        name = _safe_text(event)
        if name in ALLOWED_EVENTS and name not in out:
            out.append(name)
    return out


def _persist_supabase(row: dict) -> None:
    if not supabase:
        return
    try:
        supabase.table(TABLE).upsert(
            {
                "id": row.get("id"),
                "url": row.get("url"),
                "events": row.get("events"),
                "secret_hash": hashlib.sha256(_safe_text(row.get("secret")).encode("utf-8")).hexdigest(),
                "created_at": row.get("created_at"),
                "active": bool(row.get("active", True)),
            }
        ).execute()
    except Exception as exc:
        log.warning("webhook persist failed", error=str(exc))


def register_webhook(url: str, events: list[str], secret: str) -> dict:
    clean_url = _safe_text(url)
    clean_secret = _safe_text(secret)
    clean_events = _normalize_events(events)
    if not clean_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid webhook URL")
    if not clean_secret:
        raise HTTPException(status_code=400, detail="Secret is required")
    if not clean_events:
        raise HTTPException(status_code=400, detail="At least one valid event is required")

    rows = _load_registry()
    webhook_id = _public_id(clean_url, clean_secret)
    now = _now_iso()
    row = {
        "id": webhook_id,
        "url": clean_url,
        "events": clean_events,
        "secret": clean_secret,
        "created_at": now,
        "active": True,
    }

    replaced = False
    for idx, existing in enumerate(rows):
        if existing.get("id") == webhook_id or existing.get("url") == clean_url:
            rows[idx] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    _save_registry(rows)
    _persist_supabase(row)
    return {"id": webhook_id, "url": clean_url, "events": clean_events, "created_at": now}


def list_webhooks() -> list[dict]:
    rows = []
    for row in _load_registry():
        rows.append(
            {
                "id": row.get("id"),
                "url": row.get("url"),
                "events": row.get("events") or [],
                "created_at": row.get("created_at"),
                "active": bool(row.get("active", True)),
            }
        )
    return rows


def _signature(secret: str, body_bytes: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()


def deliver_webhook_event(event: str, data: dict) -> dict:
    clean_event = _safe_text(event)
    body = {"event": clean_event, "data": data or {}, "timestamp": _now_iso()}
    body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sent = 0
    failed = 0

    for row in _load_registry():
        if clean_event not in (row.get("events") or []) or not bool(row.get("active", True)):
            continue
        secret = _safe_text(row.get("secret"))
        sig = _signature(secret, body_bytes)
        log_row = {
            "timestamp": _now_iso(),
            "webhook_id": row.get("id"),
            "event": clean_event,
            "url": row.get("url"),
            "status": "pending",
        }
        try:
            resp = requests.post(
                row.get("url"),
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": sig,
                },
                timeout=5,
            )
            log_row["status"] = "ok" if getattr(resp, "ok", False) else "failed"
            log_row["http_status"] = getattr(resp, "status_code", None)
            if getattr(resp, "ok", False):
                sent += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            log_row["status"] = "failed"
            log_row["error"] = str(exc)
        _append_delivery_log(log_row)

    return {"event": clean_event, "sent": sent, "failed": failed, "timestamp": body["timestamp"]}


@router.post("/webhooks")
async def api_register_webhook(
    _: dict = Depends(require_public_api_key),
    body: dict = Body(...),
):
    row = register_webhook(
        url=body.get("url"),
        events=body.get("events") or [],
        secret=body.get("secret"),
    )
    return api_success(row, message="webhook registered")


@router.get("/webhooks")
async def api_list_webhooks(_: dict = Depends(require_public_api_key)):
    return api_success({"items": list_webhooks()})


@router.post("/webhooks/test")
async def api_test_webhook(
    _: dict = Depends(require_public_api_key),
    body: dict = Body(default={}),
):
    event = _safe_text(body.get("event") or "alert")
    if event not in ALLOWED_EVENTS:
        raise HTTPException(status_code=400, detail="Invalid event")
    result = deliver_webhook_event(event, body.get("data") or {"message": "test"})
    return api_success(result, message="webhook test delivered")
