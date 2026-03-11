"""Market-neutral monitor for KR long/short portfolio (Phase C-3)."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram
from quant.factors.registry import FactorContext, calc_all

load_env()
log = get_logger("neutrality_monitor")
supabase = get_supabase()

REPORT_PATH = BRAIN_PATH / "portfolio" / "neutrality_report.json"
PLAN_PATH = BRAIN_PATH / "portfolio" / "long_short_plan.json"
SHORT_TABLE = "short_positions"
FACTOR_NAMES = ["momentum_12m", "roe", "revenue_growth"]
WARN_BETA = 0.15
REBALANCE_BETA = 0.30


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _now_iso() -> str:
    return datetime.now().isoformat()


def _watchlist_sector_map() -> dict[str, str]:
    try:
        from stocks.stock_premarket import WATCHLIST

        return {str(item.get("code")): str(item.get("sector") or "") for item in WATCHLIST}
    except Exception:
        return {}


def _load_plan() -> dict:
    if not PLAN_PATH.exists():
        return {}
    try:
        payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_open_longs() -> list[dict]:
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
        log.warning("open longs load failed", error=str(exc))
        return []


def _load_open_shorts() -> list[dict]:
    if not supabase:
        return []
    try:
        return (
            supabase.table(SHORT_TABLE)
            .select("ticker,ticker_name,quantity,entry_price,current_price,closed_at")
            .is_("closed_at", "null")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        log.warning("open shorts load failed", error=str(exc))
        return []


def _latest_close(code: str, limit: int = 90) -> list[float]:
    if not supabase:
        return []
    try:
        rows = (
            supabase.table("daily_ohlcv")
            .select("date,close_price")
            .eq("stock_code", str(code))
            .order("date", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        rows.reverse()
        return [_safe_float(row.get("close_price"), 0.0) for row in rows if _safe_float(row.get("close_price"), 0.0) > 0]
    except Exception:
        return []


def _benchmark_close(limit: int = 90) -> list[float]:
    try:
        import yfinance as yf

        hist = yf.Ticker("^KS11").history(period="6mo")
        if hist is None or hist.empty or "Close" not in hist:
            return []
        closes = [float(v) for v in hist["Close"]]
        return closes[-limit:]
    except Exception as exc:
        log.warning("benchmark load failed", error=str(exc))
        return []


def _returns(closes: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(closes)):
        prev = _safe_float(closes[i - 1], 0.0)
        cur = _safe_float(closes[i], 0.0)
        if prev > 0 and cur > 0:
            out.append(cur / prev - 1.0)
    return out


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / (len(values) - 1)


def _covariance(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    xs = x[-n:]
    ys = y[-n:]
    mx = sum(xs) / n
    my = sum(ys) / n
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (n - 1)


def _estimate_beta(code: str, benchmark_returns: list[float]) -> float:
    stock_close = _latest_close(code)
    stock_returns = _returns(stock_close)
    var_b = _variance(benchmark_returns)
    if not stock_returns or var_b <= 0:
        return 1.0
    cov = _covariance(stock_returns, benchmark_returns)
    beta = cov / var_b if var_b > 0 else 1.0
    if beta == 0:
        return 1.0
    return max(-1.5, min(2.5, round(beta, 4)))


def _factor_tilt(code: str, factor_ctx: FactorContext) -> dict[str, float]:
    try:
        return calc_all(datetime.now().date().isoformat(), code, market="kr", factor_names=FACTOR_NAMES, context=factor_ctx)
    except Exception:
        return {name: 0.0 for name in FACTOR_NAMES}


def _normalize_long_rows(rows: list[dict], sector_map: dict[str, str], benchmark_returns: list[float], factor_ctx: FactorContext) -> list[dict]:
    out = []
    for row in rows:
        code = str(row.get("stock_code") or "")
        if not code:
            continue
        price = _safe_float(row.get("price"), 0.0)
        qty = _safe_float(row.get("quantity"), 0.0)
        out.append(
            {
                "code": code,
                "name": row.get("stock_name") or code,
                "side": "LONG",
                "sector": sector_map.get(code, ""),
                "market_value": price * qty,
                "beta": _estimate_beta(code, benchmark_returns),
                "factors": _factor_tilt(code, factor_ctx),
            }
        )
    return out


def _normalize_short_rows(rows: list[dict], sector_map: dict[str, str], benchmark_returns: list[float], factor_ctx: FactorContext) -> list[dict]:
    out = []
    for row in rows:
        code = str(row.get("ticker") or "")
        if not code:
            continue
        price = _safe_float(row.get("current_price") or row.get("entry_price"), 0.0)
        qty = _safe_float(row.get("quantity"), 0.0)
        out.append(
            {
                "code": code,
                "name": row.get("ticker_name") or code,
                "side": "SHORT",
                "sector": sector_map.get(code, ""),
                "market_value": price * qty,
                "beta": _estimate_beta(code, benchmark_returns),
                "factors": _factor_tilt(code, factor_ctx),
            }
        )
    return out


def _plan_fallback_positions(plan: dict, sector_map: dict[str, str]) -> tuple[list[dict], list[dict]]:
    longs = []
    for item in plan.get("long_candidates", []) or []:
        longs.append(
            {
                "code": str(item.get("code") or ""),
                "name": item.get("name") or item.get("code") or "",
                "side": "LONG",
                "sector": item.get("sector") or sector_map.get(str(item.get("code") or ""), ""),
                "market_value": _safe_float(plan.get("account_equity"), 0.0) * _safe_float(plan.get("constraints", {}).get("per_leg_weight"), 0.04),
                "beta": 1.0,
                "factors": item.get("factor_snapshot") or {},
            }
        )
    shorts = []
    for item in plan.get("short_candidates", []) or []:
        shorts.append(
            {
                "code": str(item.get("code") or ""),
                "name": item.get("name") or item.get("code") or "",
                "side": "SHORT",
                "sector": item.get("sector") or sector_map.get(str(item.get("code") or ""), ""),
                "market_value": _safe_float(plan.get("account_equity"), 0.0) * _safe_float(plan.get("constraints", {}).get("per_leg_weight"), 0.04),
                "beta": 1.0,
                "factors": item.get("factor_snapshot") or {},
            }
        )
    return longs, shorts


def build_report() -> dict:
    plan = _load_plan()
    sector_map = _watchlist_sector_map()
    benchmark_returns = _returns(_benchmark_close())
    factor_ctx = FactorContext(supabase)

    longs = _normalize_long_rows(_load_open_longs(), sector_map, benchmark_returns, factor_ctx)
    shorts = _normalize_short_rows(_load_open_shorts(), sector_map, benchmark_returns, factor_ctx)
    if not longs and not shorts and plan:
        longs, shorts = _plan_fallback_positions(plan, sector_map)

    total_long = sum(_safe_float(item.get("market_value"), 0.0) for item in longs)
    total_short = sum(_safe_float(item.get("market_value"), 0.0) for item in shorts)
    gross = total_long + total_short

    long_beta = sum(_safe_float(item.get("market_value"), 0.0) * _safe_float(item.get("beta"), 1.0) for item in longs)
    short_beta = sum(_safe_float(item.get("market_value"), 0.0) * _safe_float(item.get("beta"), 1.0) for item in shorts)
    net_beta = (long_beta - short_beta) / gross if gross > 0 else 0.0

    sector_exposure: dict[str, float] = defaultdict(float)
    for item in longs:
        sector_exposure[str(item.get("sector") or "UNKNOWN")] += _safe_float(item.get("market_value"), 0.0)
    for item in shorts:
        sector_exposure[str(item.get("sector") or "UNKNOWN")] -= _safe_float(item.get("market_value"), 0.0)
    sector_exposure = {k: round(v / gross, 6) if gross > 0 else 0.0 for k, v in sector_exposure.items()}

    factor_exposure: dict[str, float] = defaultdict(float)
    if gross > 0:
        for item in longs:
            weight = _safe_float(item.get("market_value"), 0.0) / gross
            for factor, value in (item.get("factors") or {}).items():
                factor_exposure[str(factor)] += weight * _safe_float(value, 0.0)
        for item in shorts:
            weight = _safe_float(item.get("market_value"), 0.0) / gross
            for factor, value in (item.get("factors") or {}).items():
                factor_exposure[str(factor)] -= weight * _safe_float(value, 0.0)
    factor_exposure = {k: round(v, 6) for k, v in factor_exposure.items()}

    alert_level = "STABLE"
    recommendation = ""
    if abs(net_beta) > REBALANCE_BETA:
        alert_level = "REBALANCE"
        side = "LONG" if net_beta > 0 else "SHORT"
        candidates = longs if side == "LONG" else shorts
        largest = max(candidates, key=lambda item: _safe_float(item.get("market_value"), 0.0), default={})
        recommendation = f"Trim {side} {largest.get('code', '')}".strip()
    elif abs(net_beta) > WARN_BETA:
        alert_level = "WARNING"
        recommendation = "Review net beta drift"

    return {
        "timestamp": _now_iso(),
        "net_beta": round(net_beta, 6),
        "long_market_value": round(total_long, 2),
        "short_market_value": round(total_short, 2),
        "gross_exposure": round(gross, 2),
        "sector_exposure": sector_exposure,
        "factor_exposure": factor_exposure,
        "long_count": len(longs),
        "short_count": len(shorts),
        "alert_level": alert_level,
        "recommendation": recommendation,
        "thresholds": {"warning_beta": WARN_BETA, "rebalance_beta": REBALANCE_BETA},
    }


def save_report(report: dict) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return REPORT_PATH


def maybe_notify(report: dict) -> None:
    level = str(report.get("alert_level") or "STABLE").upper()
    if level == "STABLE":
        return
    send_telegram(
        "\n".join(
            [
                "⚖️ <b>Neutrality Monitor</b>",
                f"Level: {level}",
                f"Net Beta: {float(report.get('net_beta', 0.0) or 0.0):+.3f}",
                f"Long/Short: {int(_safe_float(report.get('long_market_value'), 0.0)):,} / {int(_safe_float(report.get('short_market_value'), 0.0)):,}",
                f"Action: {report.get('recommendation') or '-'}",
            ]
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Long/short neutrality monitor")
    parser.add_argument("--no-send", action="store_true", help="skip telegram alerts")
    args = parser.parse_args()

    report = build_report()
    path = save_report(report)
    log.info("neutrality report saved", path=str(path), alert_level=report.get("alert_level"), net_beta=report.get("net_beta"))
    if not args.no_send:
        maybe_notify(report)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
