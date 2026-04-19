"""Expo push notification registry and sender (Phase F-3)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, Body, Depends, HTTPException

from api.signal_api import require_public_api_key
from common.api_utils import api_success
from common.config import BRAIN_PATH
from common.logger import get_logger
from common.supabase_client import get_supabase

router = APIRouter(prefix="/api/v1/push", tags=["public-push"])
log = get_logger("push_notifier")
supabase = get_supabase()

DEVICES_PATH = BRAIN_PATH / "push" / "devices.json"
DELIVERY_LOG_PATH = BRAIN_PATH / "push" / "delivery_log.jsonl"
TABLE = "push_devices"
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_devices() -> list[dict]:
    if not DEVICES_PATH.exists():
        return []
    try:
        payload = json.loads(DEVICES_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _save_devices(rows: list[dict]) -> Path:
    DEVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEVICES_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEVICES_PATH


def _append_delivery_log(row: dict) -> None:
    DELIVERY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DELIVERY_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _device_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _persist_supabase(row: dict) -> None:
    if not supabase:
        return
    try:
        supabase.table(TABLE).upsert(
            {
                "id": row.get("id"),
                "token": row.get("token"),
                "token_hash": hashlib.sha256(_safe_text(row.get("token")).encode("utf-8")).hexdigest(),
                "platform": row.get("platform"),
                "label": row.get("label"),
                "active": bool(row.get("active", True)),
                "updated_at": row.get("updated_at"),
            }
        ).execute()
    except Exception as exc:
        log.warning("push device persist failed", error=str(exc))


def register_push_device(token: str, platform: str = "expo", label: str = "", enabled: bool = True) -> dict:
    clean_token = _safe_text(token)
    clean_platform = _safe_text(platform or "expo").lower() or "expo"
    clean_label = _safe_text(label)
    if not clean_token.startswith("ExponentPushToken["):
        raise HTTPException(status_code=400, detail="Invalid Expo push token")

    rows = _load_devices()
    row = {
        "id": _device_id(clean_token),
        "token": clean_token,
        "platform": clean_platform,
        "label": clean_label,
        "active": bool(enabled),
        "updated_at": _now_iso(),
    }

    replaced = False
    for idx, existing in enumerate(rows):
        if existing.get("id") == row["id"] or existing.get("token") == clean_token:
            rows[idx] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    _save_devices(rows)
    _persist_supabase(row)
    return {
        "id": row["id"],
        "platform": row["platform"],
        "label": row["label"],
        "active": row["active"],
        "updated_at": row["updated_at"],
    }


def list_push_devices() -> list[dict]:
    items = []
    for row in _load_devices():
        items.append(
            {
                "id": row.get("id"),
                "platform": row.get("platform", "expo"),
                "label": row.get("label", ""),
                "active": bool(row.get("active", True)),
                "updated_at": row.get("updated_at"),
            }
        )
    return items


def send_push_notification(title: str, body: str, data: dict | None = None) -> dict:
    clean_title = _safe_text(title)
    clean_body = _safe_text(body)
    if not clean_title or not clean_body:
        raise HTTPException(status_code=400, detail="Title and body are required")

    sent = 0
    failed = 0
    responses: list[dict] = []
    payload_data = data or {}
    for row in _load_devices():
        if not bool(row.get("active", True)):
            continue
        token = _safe_text(row.get("token"))
        message = {
            "to": token,
            "title": clean_title,
            "body": clean_body,
            "sound": "default",
            "data": payload_data,
        }
        log_row = {
            "timestamp": _now_iso(),
            "device_id": row.get("id"),
            "platform": row.get("platform"),
            "status": "pending",
            "title": clean_title,
        }
        try:
            resp = requests.post(EXPO_PUSH_URL, json=message, timeout=5)
            ok = getattr(resp, "ok", False)
            parsed = {}
            try:
                parsed = resp.json()
            except Exception:
                parsed = {"raw": resp.text[:200]}
            log_row["status"] = "ok" if ok else "failed"
            log_row["http_status"] = getattr(resp, "status_code", None)
            log_row["response"] = parsed
            responses.append({"device_id": row.get("id"), "ok": ok, "response": parsed})
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            log_row["status"] = "failed"
            log_row["error"] = str(exc)
            responses.append({"device_id": row.get("id"), "ok": False, "error": str(exc)})
        _append_delivery_log(log_row)
    return {"sent": sent, "failed": failed, "responses": responses, "timestamp": _now_iso()}


@router.post("/register")
async def api_register_push(
    _: dict = Depends(require_public_api_key),
    body: dict = Body(...),
):
    row = register_push_device(
        token=body.get("token"),
        platform=body.get("platform") or "expo",
        label=body.get("label") or "",
        enabled=bool(body.get("enabled", True)),
    )
    return api_success(row, message="push device registered")


@router.get("/devices")
async def api_list_push_devices(_: dict = Depends(require_public_api_key)):
    return api_success({"items": list_push_devices()})


@router.post("/test")
async def api_test_push(
    _: dict = Depends(require_public_api_key),
    body: dict = Body(default={}),
):
    result = send_push_notification(
        title=body.get("title") or "OpenClaw Test",
        body=body.get("body") or "Push pipeline connected",
        data=body.get("data") or {"event": "test"},
    )
    return api_success(result, message="push test delivered")
