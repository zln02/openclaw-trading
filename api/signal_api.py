"""Public Signal API (Phase E-1)."""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from agents.regime_classifier import RegimeClassifier
from common.api_utils import api_success
from common.config import BRAIN_PATH, STRATEGY_JSON
from common.env_loader import load_env
from common.equity_loader import load_market_allocation, load_target_weights
from common.logger import get_logger
from common.supabase_client import get_supabase

load_env()
log = get_logger("public_signal_api")
router = APIRouter(prefix="/api/v1", tags=["public-api"])
supabase = get_supabase()

_RATE_CACHE: dict[str, list[float]] = defaultdict(list)
_API_SUPABASE_WARNED = False


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(str(raw_key or "").encode("utf-8")).hexdigest()


def _env_api_records() -> dict[str, dict]:
    records: dict[str, dict] = {}
    for raw in os.environ.get("PUBLIC_API_KEYS", "").split(","):
        key = raw.strip()
        if key:
            records[_hash_key(key)] = {"tier": "free", "source": "env"}
    for raw in os.environ.get("PUBLIC_API_KEY_HASHES", "").split(","):
        key_hash = raw.strip().lower()
        if key_hash:
            records[key_hash] = {"tier": "free", "source": "env_hash"}
    return records


def _get_api_record(api_key: str) -> dict | None:
    global _API_SUPABASE_WARNED
    key_hash = _hash_key(api_key)
    env_records = _env_api_records()
    if key_hash in env_records:
        return env_records[key_hash]

    if not supabase:
        return None
    try:
        rows = (
            supabase.table("api_keys")
            .select("id,key_hash,tier,user_email")
            .execute()
            .data
            or []
        )
        for row in rows:
            stored = str(row.get("key_hash") or "").strip().lower()
            if stored and stored == key_hash:
                return {
                    "id": row.get("id"),
                    "tier": str(row.get("tier") or "free"),
                    "user_email": row.get("user_email"),
                    "source": "supabase",
                }
    except Exception as exc:
        if not _API_SUPABASE_WARNED:
            _API_SUPABASE_WARNED = True
            log.warning("api_keys lookup failed", error=str(exc))
    return None


def _rate_limit_for_tier(tier: str) -> int:
    return 600 if str(tier or "").lower() == "pro" else 60


def require_public_api_key(
    request: Request,
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> dict:
    key = str(x_api_key or "").strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")

    record = _get_api_record(key)
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    bucket_key = _hash_key(key)
    limit = _rate_limit_for_tier(record.get("tier", "free"))
    now = time.time()
    recent = [ts for ts in _RATE_CACHE[bucket_key] if now - ts < 60]
    if len(recent) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    recent.append(now)
    _RATE_CACHE[bucket_key] = recent
    return record


def _file_updated_at(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


def _load_kr_strategy() -> dict:
    if not STRATEGY_JSON.exists():
        return {}
    try:
        payload = json.loads(STRATEGY_JSON.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_long_short_plan() -> dict:
    path = BRAIN_PATH / "portfolio" / "long_short_plan.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _kr_top_picks() -> tuple[list[dict], str | None]:
    strategy = _load_kr_strategy()
    updated_at = _file_updated_at(STRATEGY_JSON)
    factor_by_code = {
        str(item.get("code") or ""): item.get("factor_snapshot") or {}
        for item in (_load_long_short_plan().get("long_candidates") or [])
    }
    picks = []
    try:
        from stocks.ml_model import get_ml_signal
    except Exception:
        get_ml_signal = None

    for row in (strategy.get("top_picks") or [])[:5]:
        code = str(row.get("code") or "")
        ml_conf = 0.0
        if get_ml_signal is not None and code:
            try:
                ml_conf = _safe_float((get_ml_signal(code) or {}).get("confidence"), 0.0)
            except Exception:
                ml_conf = 0.0
        picks.append(
            {
                "ticker": code,
                "name": row.get("name") or code,
                "score": 80 if str(row.get("action") or "").upper() == "BUY" else 60,
                "ml_confidence": round(ml_conf, 2),
                "factors": factor_by_code.get(code, {}),
                "action": row.get("action", "WATCH"),
            }
        )
    return picks, updated_at


def _us_top_picks() -> tuple[list[dict], str | None]:
    try:
        from btc.routes.us_api import _fetch_us_signals
        payload = _fetch_us_signals()
    except Exception:
        payload = {"run_date": None, "items": []}
    items = []
    for row in (payload.get("items") or [])[:5]:
        items.append(
            {
                "ticker": row.get("symbol") or row.get("ticker") or "",
                "momentum_score": _safe_float(row.get("score"), 0.0),
                "grade": row.get("grade") or "",
            }
        )
    updated_at = str(payload.get("run_date") or "") or None
    return items, updated_at


def _regime_history_7d(current: dict) -> list[dict]:
    history: list[dict] = []
    for offset in range(6, -1, -1):
        as_of = (datetime.now().date() - timedelta(days=offset)).isoformat()
        try:
            row = RegimeClassifier().classify(as_of=as_of, use_model=False)
            history.append(
                {
                    "date": as_of,
                    "regime": row.get("regime", "TRANSITION"),
                    "confidence": round(_safe_float(row.get("confidence"), 0.5), 6),
                }
            )
        except Exception:
            history.append(
                {
                    "date": as_of,
                    "regime": current.get("regime", "TRANSITION"),
                    "confidence": round(_safe_float(current.get("confidence"), 0.5), 6),
                }
            )
    return history


@router.get("/signals/btc")
async def public_btc_signal(_: dict = Depends(require_public_api_key)):
    try:
        from btc.routes.btc_api import _compute_composite_sync

        payload = _compute_composite_sync()
    except Exception as exc:
        log.warning("btc public payload failed", error=str(exc))
        payload = {"composite": {"total": 0, "recommendation": "HOLD"}, "trend": "SIDEWAYS", "fg_value": 50}

    regime = RegimeClassifier().classify()
    data = {
        "composite_score": _safe_float((payload.get("composite") or {}).get("total"), 0.0),
        "regime": regime.get("regime", "TRANSITION"),
        "trend": payload.get("trend", "SIDEWAYS"),
        "fg_index": _safe_float(payload.get("fg_value"), 50.0),
        "recommendation": (payload.get("composite") or {}).get("recommendation", "HOLD"),
        "updated_at": datetime.now().isoformat(),
    }
    return api_success(data)


@router.get("/signals/kr")
async def public_kr_signal(_: dict = Depends(require_public_api_key)):
    picks, updated_at = _kr_top_picks()
    regime = RegimeClassifier().classify()
    return api_success(
        {
            "top_picks": picks,
            "regime": regime.get("regime", "TRANSITION"),
            "updated_at": updated_at or datetime.now().isoformat(),
        }
    )


@router.get("/signals/us")
async def public_us_signal(_: dict = Depends(require_public_api_key)):
    picks, updated_at = _us_top_picks()
    regime = RegimeClassifier().classify()
    return api_success(
        {
            "top_picks": picks,
            "regime": regime.get("regime", "TRANSITION"),
            "updated_at": updated_at or datetime.now().isoformat(),
        }
    )


@router.get("/signals/regime")
async def public_regime_signal(_: dict = Depends(require_public_api_key)):
    current = RegimeClassifier().classify()
    return api_success(
        {
            "current_regime": current.get("regime", "TRANSITION"),
            "confidence": round(_safe_float(current.get("confidence"), 0.5), 6),
            "factors": current.get("features", {}),
            "history_7d": _regime_history_7d(current),
        }
    )


@router.get("/portfolio/allocation")
async def public_portfolio_allocation(_: dict = Depends(require_public_api_key)):
    alloc = load_market_allocation()
    allocation = alloc.get("allocation") or {}
    if not allocation:
        target = load_target_weights()
        class_weights = target.get("class_weights") or {}
        allocation = {
            "btc": _safe_float(class_weights.get("CRYPTO"), 0.0),
            "kr": _safe_float(class_weights.get("KR"), 0.0),
            "us": _safe_float(class_weights.get("US"), 0.0),
            "cash": 0.0,
        }
    updated_at = _file_updated_at(BRAIN_PATH / "portfolio" / "market_allocation.json")
    rebalance_due = True
    if updated_at:
        try:
            ts = datetime.fromisoformat(updated_at)
            rebalance_due = (datetime.now() - ts) > timedelta(days=7)
        except Exception:
            rebalance_due = True
    return api_success(
        {
            "btc_pct": round(_safe_float(allocation.get("btc"), 0.0) * 100, 2),
            "kr_pct": round(_safe_float(allocation.get("kr"), 0.0) * 100, 2),
            "us_pct": round(_safe_float(allocation.get("us"), 0.0) * 100, 2),
            "cash_pct": round(_safe_float(allocation.get("cash"), 0.0) * 100, 2),
            "rebalance_due": rebalance_due,
            "updated_at": updated_at or datetime.now().isoformat(),
        }
    )
