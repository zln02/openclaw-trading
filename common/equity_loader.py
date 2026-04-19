from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from common.config import BRAIN_PATH
from common.supabase_client import get_supabase
from common.utils import safe_float as _safe_float
from common.utils import utc_now as _utc_now


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        try:
            return datetime.fromisoformat(text[:19])
        except Exception:
            return None


def _trade_day(value: Any) -> str:
    dt = _parse_dt(value) or _utc_now()
    return dt.date().isoformat()


def _state_file() -> Path:
    return BRAIN_PATH / "risk" / "drawdown_state.json"


def _snapshot_file(market: str) -> Path:
    return BRAIN_PATH / "equity" / f"{str(market).lower()}.jsonl"


def load_drawdown_state(market: str) -> dict:
    path = _state_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = payload.get(str(market).lower(), {})
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def append_equity_snapshot(market: str, equity: float, metadata: Optional[dict] = None) -> None:
    eq = _safe_float(equity, 0.0)
    if eq <= 0:
        return
    path = _snapshot_file(market)
    # 깨진 심볼릭 링크 처리: 부모 디렉토리가 실제로 존재하는지 확인 후 생성
    parent = path.parent
    if not parent.exists() and not parent.is_symlink():
        parent.mkdir(parents=True, exist_ok=True)
    elif parent.is_symlink() and not parent.exists():
        # 깨진 심볼릭 링크 경우 — 제거하고 실제 디렉토리 생성
        try:
            parent.unlink()
            parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            # mkdir 실패 시 무시 — 파일 쓰기는 시도
            pass
    row = {
        "timestamp": _utc_now().isoformat(),
        "date": _utc_now().date().isoformat(),
        "equity": round(eq, 6),
        "market": str(market).lower(),
        "metadata": metadata or {},
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_equity_snapshots(market: str, lookback_days: int = 90) -> list[dict]:
    path = _snapshot_file(market)
    if not path.exists():
        return []

    cutoff = (_utc_now().date() - timedelta(days=max(lookback_days, 30))).isoformat()
    latest_by_day: dict[str, float] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            day = str(row.get("date") or "")[:10]
            if not day or day < cutoff:
                continue
            equity = _safe_float(row.get("equity"), 0.0)
            if equity > 0:
                latest_by_day[day] = equity
    except Exception:
        return []

    return [{"date": day, "equity": latest_by_day[day]} for day in sorted(latest_by_day.keys())]


def save_drawdown_state(market: str, state: dict) -> None:
    path = _state_file()
    # 깨진 심볼릭 링크 처리
    parent = path.parent
    if not parent.exists() and not parent.is_symlink():
        parent.mkdir(parents=True, exist_ok=True)
    elif parent.is_symlink() and not parent.exists():
        try:
            parent.unlink()
            parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    payload = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    payload[str(market).lower()] = state or {}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _closed_trade_rows(market: str, supabase_client=None, limit: int = 300):
    sb = supabase_client or get_supabase()
    if not sb:
        return []

    market = str(market).lower()
    try:
        if market == "btc":
            return (
                sb.table("btc_position")
                .select("entry_time,exit_time,entry_krw,pnl,pnl_pct,status")
                .eq("status", "CLOSED")
                .order("exit_time", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        if market == "kr":
            return (
                sb.table("trade_executions")
                .select("created_at,trade_type,price,entry_price,quantity,result,stock_code,pnl_pct")
                .eq("trade_type", "SELL")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        if market == "us":
            return (
                sb.table("us_trade_executions")
                .select("created_at,trade_type,price,entry_price,quantity,result,symbol")
                .eq("trade_type", "SELL")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
    except Exception:
        return []
    return []


def load_recent_trades(market: str, limit: int = 100, supabase_client=None) -> list[dict]:
    rows = _closed_trade_rows(market, supabase_client=supabase_client, limit=limit)
    out: list[dict] = []
    for row in rows:
        pnl_pct = _safe_float(row.get("pnl_pct"), None)
        if pnl_pct is None:
            entry = _safe_float(row.get("entry_price") or row.get("entry_krw"), 0.0)
            if str(market).lower() == "btc":
                base = _safe_float(row.get("entry_krw"), 0.0)
                pnl = _safe_float(row.get("pnl"), 0.0)
                pnl_pct = (pnl / base * 100.0) if base > 0 else 0.0
            else:
                price = _safe_float(row.get("price"), 0.0)
                qty = _safe_float(row.get("quantity"), 0.0)
                pnl_pct = ((price - entry) / entry * 100.0) if entry > 0 and qty > 0 else 0.0
        out.append(
            {
                "date": _trade_day(row.get("exit_time") or row.get("created_at")),
                "pnl_pct": pnl_pct / 100.0 if abs(pnl_pct) > 1 else pnl_pct,
            }
        )
    return out


def load_equity_curve(market: str, lookback_days: int = 90, supabase_client=None) -> list[dict]:
    snapshots = _load_equity_snapshots(market, lookback_days=lookback_days)
    if len(snapshots) >= 5:
        return snapshots

    trades = load_recent_trades(market, limit=max(lookback_days * 4, 120), supabase_client=supabase_client)
    if not trades:
        return []

    by_day: dict[str, float] = defaultdict(float)
    for trade in trades:
        by_day[str(trade["date"])] += _safe_float(trade.get("pnl_pct"), 0.0)

    today = _utc_now().date()
    start = today - timedelta(days=max(lookback_days, 30))
    equity = 1.0
    curve: list[dict] = []
    for offset in range((today - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        equity *= 1.0 + by_day.get(day, 0.0)
        curve.append({"date": day, "equity": round(equity, 6)})
    return curve


def load_target_weights() -> dict:
    path = BRAIN_PATH / "portfolio" / "target_weights.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_market_allocation() -> dict:
    path = BRAIN_PATH / "portfolio" / "market_allocation.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def get_market_allocation_weight(market: str) -> Optional[float]:
    market_key = str(market or "").lower()
    payload = load_market_allocation()
    allocation = payload.get("allocation") or {}
    if not isinstance(allocation, dict):
        return None
    return _safe_float(allocation.get(market_key), None)


def get_effective_market_weight(market: str) -> Optional[float]:
    dynamic_weight = get_market_allocation_weight(market)
    target_weight = get_market_target_weight(market)
    weights = [w for w in (dynamic_weight, target_weight) if w is not None and w > 0]
    if not weights:
        return None
    return min(weights)


def get_market_target_weight(market: str) -> Optional[float]:
    market = str(market).upper()
    payload = load_target_weights()
    class_weights = payload.get("class_weights") or {}
    if market == "BTC":
        return _safe_float(class_weights.get("CRYPTO"), None)
    if market == "KR":
        return _safe_float(class_weights.get("KR"), None)
    if market == "US":
        return _safe_float(class_weights.get("US"), None)
    return None


def load_all_positions(supabase_client=None) -> list[dict]:
    sb = supabase_client or get_supabase()
    if not sb:
        return []

    positions: list[dict] = []

    try:
        btc_rows = (
            sb.table("btc_position")
            .select("entry_price,quantity,status")
            .eq("status", "OPEN")
            .execute()
            .data
            or []
        )
        for row in btc_rows:
            positions.append(
                {
                    "symbol": "BTC",
                    "market": "BTC",
                    "asset_class": "CRYPTO",
                    "quantity": _safe_float(row.get("quantity"), 0.0),
                    "price": _safe_float(row.get("entry_price"), 0.0),
                    "market_value": _safe_float(row.get("quantity"), 0.0) * _safe_float(row.get("entry_price"), 0.0),
                }
            )
    except Exception:
        pass

    try:
        kr_rows = (
            sb.table("trade_executions")
            .select("stock_code,quantity,price,result")
            .eq("result", "OPEN")
            .execute()
            .data
            or []
        )
        for row in kr_rows:
            code = str(row.get("stock_code") or "").strip()
            if not code:
                continue
            positions.append(
                {
                    "symbol": f"A{code}",
                    "market": "KR",
                    "asset_class": "KR",
                    "quantity": _safe_float(row.get("quantity"), 0.0),
                    "price": _safe_float(row.get("price"), 0.0),
                    "market_value": _safe_float(row.get("quantity"), 0.0) * _safe_float(row.get("price"), 0.0),
                }
            )
    except Exception:
        pass

    try:
        us_rows = (
            sb.table("us_trade_executions")
            .select("symbol,quantity,price,result")
            .eq("result", "OPEN")
            .execute()
            .data
            or []
        )
        for row in us_rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            positions.append(
                {
                    "symbol": symbol,
                    "market": "US",
                    "asset_class": "US",
                    "quantity": _safe_float(row.get("quantity"), 0.0),
                    "price": _safe_float(row.get("price"), 0.0),
                    "market_value": _safe_float(row.get("quantity"), 0.0) * _safe_float(row.get("price"), 0.0),
                }
            )
    except Exception:
        pass

    return positions
