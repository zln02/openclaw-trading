#!/usr/bin/env python3
"""KR long/short portfolio simulator (Phase C-2).

Default mode is DRY-RUN and writes candidate plans to brain/portfolio.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.regime_classifier import RegimeClassifier
from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram
from quant.factors.registry import FactorContext, calc_all

load_env()
log = get_logger("long_short_agent")
supabase = get_supabase()
_SUPABASE_DOWN = False

try:
    from stock_premarket import WATCHLIST
except Exception:
    WATCHLIST = []

DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"
PLAN_PATH = BRAIN_PATH / "portfolio" / "long_short_plan.json"
SHORT_TABLE = "short_positions"
FACTOR_NAMES = ["momentum_12m", "roe", "revenue_growth"]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _calc_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for i in range(-period, 0):
        diff = float(closes[i]) - float(closes[i - 1])
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss <= 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _calc_volume_ratio(rows: list[dict], period: int = 20) -> float:
    if len(rows) < period + 1:
        return 1.0
    vols = [_safe_float(r.get("volume"), 0.0) for r in rows]
    recent = vols[-1]
    base = vols[-period - 1 : -1]
    avg = sum(base) / max(len(base), 1)
    if avg <= 0:
        return 1.0
    return round(recent / avg, 4)


def _load_daily_rows(code: str, limit: int = 260) -> list[dict]:
    global _SUPABASE_DOWN
    if _SUPABASE_DOWN:
        return []
    if not supabase:
        return []
    try:
        rows = (
            supabase.table("daily_ohlcv")
            .select("date,open_price,high_price,low_price,close_price,volume")
            .eq("stock_code", str(code))
            .order("date", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        rows.reverse()
        return rows
    except Exception as exc:
        _SUPABASE_DOWN = True
        log.warning("daily rows load failed; suppressing further Supabase reads", stock_code=str(code), error=str(exc))
        return []


def _get_last_price(code: str) -> float:
    rows = _load_daily_rows(code, limit=5)
    if not rows:
        return 0.0
    return _safe_float(rows[-1].get("close_price"), 0.0)


def _get_watchlist() -> list[dict]:
    global _SUPABASE_DOWN
    if _SUPABASE_DOWN:
        return [{"code": str(w.get("code")), "name": str(w.get("name")), "sector": str(w.get("sector", ""))} for w in WATCHLIST]
    if supabase:
        try:
            rows = (
                supabase.table("top50_stocks")
                .select("stock_code,stock_name")
                .limit(50)
                .execute()
                .data
                or []
            )
            if rows:
                sector_map = {str(item.get("code")): item.get("sector", "") for item in WATCHLIST}
                return [
                    {
                        "code": str(row.get("stock_code") or ""),
                        "name": str(row.get("stock_name") or row.get("stock_code") or ""),
                        "sector": sector_map.get(str(row.get("stock_code") or ""), ""),
                    }
                    for row in rows
                    if row.get("stock_code")
                ]
        except Exception as exc:
            _SUPABASE_DOWN = True
            log.warning("top50_stocks load failed", error=str(exc))
    return [{"code": str(w.get("code")), "name": str(w.get("name")), "sector": str(w.get("sector", ""))} for w in WATCHLIST]


def _load_today_strategy() -> dict:
    path = Path(__file__).resolve().parent / "today_strategy.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if payload.get("date") != _today_iso():
        return {}
    return payload


def _load_account_equity() -> float:
    global _SUPABASE_DOWN
    if _SUPABASE_DOWN:
        return 10_000_000.0
    if not supabase:
        return 10_000_000.0
    try:
        rows = (
            supabase.table("trade_executions")
            .select("price,quantity,result")
            .eq("result", "OPEN")
            .execute()
            .data
            or []
        )
        open_value = sum(_safe_float(r.get("price"), 0.0) * _safe_float(r.get("quantity"), 0.0) for r in rows)
        return max(10_000_000.0, open_value * 2.0 if open_value > 0 else 10_000_000.0)
    except Exception:
        _SUPABASE_DOWN = True
        return 10_000_000.0


def _score_long_candidate(stock: dict, strategy_bias: float, factor_ctx: FactorContext) -> dict | None:
    code = str(stock.get("code") or "").strip()
    if not code:
        return None
    rows = _load_daily_rows(code)
    if len(rows) < 30:
        return None
    closes = [_safe_float(r.get("close_price"), 0.0) for r in rows if _safe_float(r.get("close_price"), 0.0) > 0]
    if len(closes) < 30:
        return None
    ret_20d = (closes[-1] / closes[-21] - 1.0) * 100.0 if len(closes) >= 21 and closes[-21] > 0 else 0.0
    ret_5d = (closes[-1] / closes[-6] - 1.0) * 100.0 if len(closes) >= 6 and closes[-6] > 0 else 0.0
    rsi = _calc_rsi(closes)
    vol_ratio = _calc_volume_ratio(rows)
    factors = calc_all(_today_iso(), code, market="kr", factor_names=FACTOR_NAMES, context=factor_ctx)
    factor_boost = max(0.0, _safe_float(factors.get("momentum_12m")) * 0.1 + _safe_float(factors.get("roe")) * 0.2)
    score = strategy_bias + ret_20d * 0.9 + ret_5d * 0.5 + factor_boost + max(0.0, (60.0 - rsi)) * 0.15 + vol_ratio * 4.0
    return {
        "code": code,
        "name": stock.get("name") or code,
        "sector": stock.get("sector") or "",
        "price": round(closes[-1], 2),
        "ret_5d": round(ret_5d, 3),
        "ret_20d": round(ret_20d, 3),
        "rsi": rsi,
        "vol_ratio": vol_ratio,
        "factor_snapshot": factors,
        "score": round(score, 4),
        "source": "STRATEGY" if strategy_bias > 0 else "MOMENTUM",
    }


def _select_long_candidates(universe: list[dict], factor_ctx: FactorContext) -> list[dict]:
    strategy = _load_today_strategy()
    bias_by_code: dict[str, float] = {}
    for pick in strategy.get("top_picks", []) if isinstance(strategy.get("top_picks"), list) else []:
        code = str(pick.get("code") or "").strip()
        action = str(pick.get("action") or "").upper()
        if not code:
            continue
        if action == "BUY":
            bias_by_code[code] = 40.0
        elif action == "WATCH":
            bias_by_code[code] = 20.0

    scored: list[dict] = []
    for stock in universe:
        candidate = _score_long_candidate(stock, bias_by_code.get(str(stock.get("code")), 0.0), factor_ctx)
        if candidate:
            scored.append(candidate)
    scored.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    picks: list[dict] = []
    sector_counts: dict[str, int] = defaultdict(int)
    for item in scored:
        sector = str(item.get("sector") or "")
        if sector and sector_counts[sector] >= 2:
            continue
        picks.append(item)
        if sector:
            sector_counts[sector] += 1
        if len(picks) >= 5:
            break
    if not picks and strategy:
        watch_map = {str(item.get("code")): item for item in universe}
        for pick in strategy.get("top_picks", []):
            action = str(pick.get("action") or "").upper()
            if action not in {"BUY", "WATCH"}:
                continue
            code = str(pick.get("code") or "")
            stock = watch_map.get(code, {})
            picks.append(
                {
                    "code": code,
                    "name": pick.get("name") or stock.get("name") or code,
                    "sector": stock.get("sector") or "",
                    "price": 0.0,
                    "ret_5d": 0.0,
                    "ret_20d": 0.0,
                    "rsi": 50.0,
                    "vol_ratio": 1.0,
                    "factor_snapshot": {},
                    "score": bias_by_code.get(code, 0.0),
                    "source": "STRATEGY_FALLBACK",
                }
            )
            if len(picks) >= 5:
                break
    return picks


def _select_short_candidates(universe: list[dict], long_candidates: list[dict], factor_ctx: FactorContext) -> list[dict]:
    sector_load = defaultdict(int)
    for item in long_candidates:
        sector = str(item.get("sector") or "")
        if sector:
            sector_load[sector] += 1

    scored: list[dict] = []
    for stock in universe:
        code = str(stock.get("code") or "").strip()
        if not code:
            continue
        rows = _load_daily_rows(code)
        if len(rows) < 260:
            continue
        closes = [_safe_float(r.get("close_price"), 0.0) for r in rows if _safe_float(r.get("close_price"), 0.0) > 0]
        if len(closes) < 60:
            continue
        rsi = _calc_rsi(closes)
        vol_ratio = _calc_volume_ratio(rows)
        if rsi <= 70 or vol_ratio >= 0.5:
            continue
        factors = calc_all(_today_iso(), code, market="kr", factor_names=FACTOR_NAMES, context=factor_ctx)
        composite = (
            _safe_float(factors.get("momentum_12m")) * 0.5
            + _safe_float(factors.get("roe")) * 0.3
            + _safe_float(factors.get("revenue_growth")) * 0.2
        )
        scored.append(
            {
                "code": code,
                "name": stock.get("name") or code,
                "sector": stock.get("sector") or "",
                "price": round(closes[-1], 2),
                "rsi": rsi,
                "vol_ratio": vol_ratio,
                "factor_snapshot": factors,
                "factor_composite": round(composite, 4),
            }
        )

    scored.sort(key=lambda item: item.get("factor_composite", 0.0))
    pool_size = max(5, int(round(len(scored) * 0.1)))
    bottom_pool = scored[:pool_size]
    picks: list[dict] = []
    for item in bottom_pool:
        sector = str(item.get("sector") or "")
        if sector and sector_load[sector] >= 2:
            continue
        picks.append(item)
        if sector:
            sector_load[sector] += 1
        if len(picks) >= 5:
            break
    return picks


def _load_open_kr_positions() -> list[dict]:
    global _SUPABASE_DOWN
    if _SUPABASE_DOWN:
        return []
    if not supabase:
        return []
    try:
        return (
            supabase.table("trade_executions")
            .select("stock_code,stock_name,quantity,price,result")
            .eq("result", "OPEN")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        _SUPABASE_DOWN = True
        log.warning("open kr positions load failed", error=str(exc))
        return []


def _load_open_short_positions() -> list[dict]:
    global _SUPABASE_DOWN
    if _SUPABASE_DOWN:
        return []
    if not supabase:
        return []
    try:
        return (
            supabase.table(SHORT_TABLE)
            .select("id,ticker,ticker_name,entry_price,current_price,quantity,side,created_at,closed_at")
            .is_("closed_at", "null")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        _SUPABASE_DOWN = True
        log.warning("open short positions load failed", error=str(exc))
        return []


def _close_short_position(row: dict, reason: str) -> None:
    if not supabase:
        return
    code = str(row.get("ticker") or "")
    current_price = _get_last_price(code) or _safe_float(row.get("current_price"), 0.0)
    entry_price = _safe_float(row.get("entry_price"), 0.0)
    pnl_pct = ((entry_price - current_price) / entry_price * 100.0) if entry_price > 0 and current_price > 0 else 0.0
    try:
        supabase.table(SHORT_TABLE).update(
            {
                "current_price": current_price,
                "pnl_pct": round(pnl_pct, 4),
                "close_reason": reason,
                "closed_at": _now_iso(),
            }
        ).eq("id", row.get("id")).execute()
    except Exception as exc:
        log.warning("close short position failed", ticker=code, error=str(exc))


def _save_short_position(candidate: dict, quantity: int) -> None:
    if not supabase or quantity <= 0:
        return
    payload = {
        "ticker": candidate.get("code"),
        "ticker_name": candidate.get("name"),
        "entry_price": candidate.get("price"),
        "current_price": candidate.get("price"),
        "quantity": quantity,
        "side": "SHORT",
        "pnl_pct": 0.0,
        "factor_snapshot": candidate.get("factor_snapshot") or {},
        "created_at": _now_iso(),
    }
    try:
        supabase.table(SHORT_TABLE).insert(payload).execute()
    except Exception as exc:
        log.warning("save short position failed", ticker=str(candidate.get("code")), error=str(exc))


def build_plan() -> dict:
    regime = RegimeClassifier().classify()
    factor_ctx = FactorContext(supabase)
    universe = _get_watchlist()
    long_candidates = _select_long_candidates(universe, factor_ctx)
    short_candidates = _select_short_candidates(universe, long_candidates, factor_ctx)
    account_equity = _load_account_equity()
    per_leg_weight = 0.04
    long_budget = account_equity * per_leg_weight * len(long_candidates)
    short_budget = min(account_equity * per_leg_weight * len(short_candidates), long_budget * 1.1 if long_budget > 0 else 0.0)

    plan = {
        "timestamp": _now_iso(),
        "mode": "DRY_RUN" if DRY_RUN else "LIVE",
        "regime": regime.get("regime", "UNKNOWN"),
        "regime_source": regime.get("source", "UNKNOWN"),
        "account_equity": round(account_equity, 2),
        "constraints": {
            "per_leg_weight": per_leg_weight,
            "max_long_positions": 5,
            "max_short_positions": 5,
            "max_short_to_long": 1.1,
            "short_stop_loss_pct": 5.0,
        },
        "long_candidates": long_candidates,
        "short_candidates": short_candidates,
        "long_notional": round(long_budget, 2),
        "short_notional": round(short_budget, 2),
        "beta_target": "market_neutral",
        "open_longs": _load_open_kr_positions(),
        "open_shorts": _load_open_short_positions(),
    }
    return plan


def save_plan(plan: dict) -> Path:
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return PLAN_PATH


def execute_plan(plan: dict) -> dict:
    regime = str(plan.get("regime") or "UNKNOWN").upper()
    if regime == "CRISIS":
        for row in plan.get("open_shorts", []):
            _close_short_position(row, reason="CRISIS_REGIME")
        return {"result": "CRISIS_CLOSE_ONLY", "closed": len(plan.get("open_shorts", []))}

    long_candidates = plan.get("long_candidates", [])
    short_candidates = plan.get("short_candidates", [])
    if not long_candidates or not short_candidates:
        return {"result": "INSUFFICIENT_CANDIDATES"}

    short_budget = _safe_float(plan.get("short_notional"), 0.0)
    if short_budget <= 0:
        return {"result": "NO_SHORT_BUDGET"}

    notional_per_short = short_budget / max(len(short_candidates), 1)
    opened = 0
    for candidate in short_candidates:
        price = _safe_float(candidate.get("price"), 0.0)
        if price <= 0:
            continue
        quantity = int(notional_per_short // price)
        if quantity <= 0:
            continue
        if not DRY_RUN:
            log.warning("live short execution not implemented", ticker=str(candidate.get("code")))
            continue
        _save_short_position(candidate, quantity)
        opened += 1

    return {
        "result": "OK",
        "opened_shorts": opened,
        "target_short_count": len(short_candidates),
        "target_long_count": len(long_candidates),
    }


def send_summary(plan: dict, result: dict) -> None:
    lines = [
        "⚖️ <b>KR Long/Short Plan</b>",
        f"Mode: {plan.get('mode')}",
        f"Regime: {plan.get('regime')}",
        f"Long {len(plan.get('long_candidates', []))} / Short {len(plan.get('short_candidates', []))}",
        f"Long Notional: {int(_safe_float(plan.get('long_notional'), 0.0)):,} KRW",
        f"Short Notional: {int(_safe_float(plan.get('short_notional'), 0.0)):,} KRW",
        f"Result: {result.get('result')}",
    ]
    send_telegram("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="KR long/short simulator")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "plan", "status"])
    parser.add_argument("--no-send", action="store_true", help="skip telegram summary")
    args = parser.parse_args()

    plan = build_plan()
    path = save_plan(plan)

    if args.command == "plan":
        print(path)
        return 0

    if args.command == "status":
        print(json.dumps({"plan_path": str(path), "open_shorts": plan.get("open_shorts", [])}, ensure_ascii=False, indent=2))
        return 0

    result = execute_plan(plan)
    summary = {"plan_path": str(path), **result}
    log.info("long short cycle completed", **summary)
    if not args.no_send:
        send_summary(plan, result)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
