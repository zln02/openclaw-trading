"""Cross-market performance scoring → brain/portfolio/market_allocation.json 생성.

매일 07:00 cron으로 실행. 최근 90일 closed trade에서 시장별 score를 계산하여
market_allocation.json에 저장. equity_loader.get_market_allocation_weight()에서 소비.

Score 계산:
  raw_score = 0.5 * win_rate + 0.3 * mean_pnl_norm + 0.2 * sharpe_proxy
  allocation = softmax(raw_scores)  # 합계 = 1.0
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase

load_env()
log = get_logger("cross_market_manager")

OUTPUT_PATH = BRAIN_PATH / "portfolio" / "market_allocation.json"
LOOKBACK_DAYS = 90
MIN_TRADES = 3  # score 계산에 필요한 최소 거래 수


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _load_closed_trades(sb, market: str) -> list[dict]:
    """시장별 closed trade 조회 → [{'pnl_pct': float}, ...]"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    try:
        if market == "btc":
            rows = (
                sb.table("btc_position")
                .select("pnl,entry_krw,pnl_pct")
                .eq("status", "CLOSED")
                .gte("exit_time", cutoff)
                .execute()
                .data or []
            )
            out = []
            for r in rows:
                p = _safe_float(r.get("pnl_pct"))
                if p == 0.0 and r.get("entry_krw"):
                    base = _safe_float(r.get("entry_krw"))
                    pnl = _safe_float(r.get("pnl"))
                    p = (pnl / base * 100.0) if base > 0 else 0.0
                out.append({"pnl_pct": p})
            return out

        if market == "kr":
            rows = (
                sb.table("trade_executions")
                .select("pnl_pct,price,entry_price,quantity")
                .eq("trade_type", "SELL")
                .gte("created_at", cutoff)
                .execute()
                .data or []
            )
            out = []
            for r in rows:
                p = _safe_float(r.get("pnl_pct"))
                if p == 0.0:
                    ep = _safe_float(r.get("entry_price"))
                    cp = _safe_float(r.get("price"))
                    p = ((cp - ep) / ep * 100.0) if ep > 0 else 0.0
                out.append({"pnl_pct": p})
            return out

        if market == "us":
            rows = (
                sb.table("us_trade_executions")
                .select("pnl_usd,price,entry_price,quantity")
                .eq("trade_type", "SELL")
                .gte("created_at", cutoff)
                .execute()
                .data or []
            )
            out = []
            for r in rows:
                ep = _safe_float(r.get("entry_price"))
                cp = _safe_float(r.get("price"))
                p = ((cp - ep) / ep * 100.0) if ep > 0 else 0.0
                out.append({"pnl_pct": p})
            return out
    except Exception as e:
        log.warning(f"{market} trade load failed: {e}")
    return []


def _compute_score(trades: list[dict]) -> dict:
    """win_rate, mean_pnl, sharpe_proxy → raw_score 반환."""
    pnls = [_safe_float(t.get("pnl_pct")) for t in trades]
    n = len(pnls)
    if n < MIN_TRADES:
        return {"n": n, "win_rate": 0.0, "mean_pnl": 0.0, "sharpe": 0.0, "raw_score": 0.0}

    win_rate = sum(1 for p in pnls if p > 0) / n
    mean_pnl = sum(pnls) / n
    std_pnl = (sum((p - mean_pnl) ** 2 for p in pnls) / n) ** 0.5
    sharpe = (mean_pnl / std_pnl) if std_pnl > 0 else 0.0

    # mean_pnl 정규화: -20%~+20% 범위를 0~1로 클램프
    mean_pnl_norm = max(0.0, min(1.0, (mean_pnl + 20.0) / 40.0))
    sharpe_norm = max(0.0, min(1.0, (sharpe + 3.0) / 6.0))

    raw_score = 0.5 * win_rate + 0.3 * mean_pnl_norm + 0.2 * sharpe_norm
    return {
        "n": n,
        "win_rate": round(win_rate, 4),
        "mean_pnl": round(mean_pnl, 4),
        "sharpe": round(sharpe, 4),
        "raw_score": round(raw_score, 6),
    }


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    """score → allocation weight (합계=1.0). 모두 0이면 균등 배분."""
    vals = list(scores.values())
    if all(v == 0.0 for v in vals):
        equal = round(1.0 / len(scores), 6)
        return {k: equal for k in scores}
    max_v = max(vals)
    exps = {k: math.exp(v - max_v) for k, v in scores.items()}
    total = sum(exps.values())
    return {k: round(e / total, 6) for k, e in exps.items()}


def run() -> dict:
    sb = get_supabase()
    if not sb:
        log.error("Supabase 미연결 — market_allocation 생성 불가")
        return {}

    markets = ["btc", "kr", "us"]
    stats: dict[str, dict] = {}
    raw_scores: dict[str, float] = {}

    for mkt in markets:
        trades = _load_closed_trades(sb, mkt)
        s = _compute_score(trades)
        stats[mkt] = s
        raw_scores[mkt] = s["raw_score"]
        log.info(f"{mkt}: n={s['n']} win={s['win_rate']:.2%} mean={s['mean_pnl']:.2f}% score={s['raw_score']:.4f}")

    allocation = _softmax(raw_scores)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "allocation": allocation,
        "stats": stats,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"market_allocation.json 저장: {allocation}")
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
