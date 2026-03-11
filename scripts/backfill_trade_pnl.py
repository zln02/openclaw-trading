#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.env_loader import load_env
from common.supabase_client import get_supabase

load_env()

KR_FEE = 0.00015 + 0.00015 + 0.0018
US_FEE = 0.001


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _calc_kr_pnl_pct(row: dict) -> float | None:
    entry = _safe_float(row.get("entry_price"))
    exit_price = _safe_float(row.get("price"))
    if entry <= 0 or exit_price <= 0:
        return None
    return round(((exit_price - entry) / entry - KR_FEE) * 100.0, 4)


def _calc_us_pnl_pct(row: dict) -> float | None:
    entry = _safe_float(row.get("price"))
    exit_price = _safe_float(row.get("exit_price"))
    if entry <= 0 or exit_price <= 0:
        return None
    return round(((exit_price - entry) / entry - US_FEE) * 100.0, 4)


def backfill_kr(supabase, apply: bool = False, limit: int = 1000) -> dict:
    rows = (
        supabase.table("trade_executions")
        .select("trade_id,trade_type,result,entry_price,price,pnl_pct")
        .eq("trade_type", "SELL")
        .eq("result", "CLOSED")
        .order("trade_id", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )

    scanned = len(rows)
    candidates = 0
    updated = 0
    samples = []

    for row in rows:
        if row.get("pnl_pct") is not None:
            continue
        pnl_pct = _calc_kr_pnl_pct(row)
        if pnl_pct is None:
            continue
        candidates += 1
        if len(samples) < 5:
            samples.append({"trade_id": row.get("trade_id"), "pnl_pct": pnl_pct})
        if apply:
            supabase.table("trade_executions").update({"pnl_pct": pnl_pct}).eq("trade_id", row["trade_id"]).execute()
            updated += 1

    return {
        "market": "kr",
        "scanned": scanned,
        "candidates": candidates,
        "updated": updated,
        "applied": apply,
        "samples": samples,
    }


def backfill_us(supabase, apply: bool = False, limit: int = 1000) -> dict:
    rows = (
        supabase.table("us_trade_executions")
        .select("id,result,price,exit_price,pnl_pct")
        .eq("result", "CLOSED")
        .order("id", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )

    scanned = len(rows)
    candidates = 0
    updated = 0
    samples = []

    for row in rows:
        if row.get("pnl_pct") is not None:
            continue
        pnl_pct = _calc_us_pnl_pct(row)
        if pnl_pct is None:
            continue
        candidates += 1
        if len(samples) < 5:
            samples.append({"id": row.get("id"), "pnl_pct": pnl_pct})
        if apply:
            supabase.table("us_trade_executions").update({"pnl_pct": pnl_pct}).eq("id", row["id"]).execute()
            updated += 1

    return {
        "market": "us",
        "scanned": scanned,
        "candidates": candidates,
        "updated": updated,
        "applied": apply,
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing pnl_pct for KR/US trades")
    parser.add_argument("--market", choices=["kr", "us", "all"], default="all")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    supabase = get_supabase()
    if not supabase:
        print(json.dumps({"ok": False, "error": "supabase unavailable"}, ensure_ascii=False, indent=2))
        return 1

    results = []
    if args.market in ("kr", "all"):
        results.append(backfill_kr(supabase, apply=args.apply, limit=args.limit))
    if args.market in ("us", "all"):
        results.append(backfill_us(supabase, apply=args.apply, limit=args.limit))

    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
