"""Slippage tracking utilities (Phase 13).

- Record expected vs actual execution prices
- Persist to Supabase `execution_quality` when available
- Keep local JSONL fallback for offline analysis
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase

load_env()
log = get_logger("slippage_tracker")

DEFAULT_TABLE = "execution_quality"
LOCAL_DIR = BRAIN_PATH / "execution-quality"
_SUPABASE_AUTO = object()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_side(side: str) -> str:
    s = str(side or "").strip().lower()
    if s in {"buy", "sell"}:
        return s
    raise ValueError(f"invalid side: {side}")


def _month_start_end(year_month: str) -> tuple[str, str]:
    base = datetime.strptime(f"{year_month}-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
    next_month = (base.replace(day=28) + timedelta(days=4)).replace(day=1)
    return base.isoformat(), next_month.isoformat()


def _in_range(ts: str, start_iso: str, end_iso: str) -> bool:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        s = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return s <= t < e
    except Exception:
        return False


def compute_slippage_metrics(expected_price: float, actual_price: float, side: str) -> dict:
    exp = _safe_float(expected_price, 0.0)
    act = _safe_float(actual_price, 0.0)
    sd = _normalize_side(side)
    if exp <= 0 or act <= 0:
        return {
            "slippage_pct": 0.0,
            "slippage_bps": 0.0,
            "adverse_slippage_bps": 0.0,
            "abs_slippage_bps": 0.0,
            "is_valid": False,
        }

    raw = (act / exp) - 1.0
    slippage_bps = raw * 10000.0
    adverse_bps = slippage_bps if sd == "buy" else -slippage_bps

    return {
        "slippage_pct": round(raw * 100.0, 6),
        "slippage_bps": round(slippage_bps, 6),
        "adverse_slippage_bps": round(adverse_bps, 6),
        "abs_slippage_bps": round(abs(slippage_bps), 6),
        "is_valid": True,
    }


@dataclass
class ExecutionFill:
    symbol: str
    side: str
    qty: float
    expected_price: float
    actual_price: float
    market: str = "auto"
    route: str = "MARKET"
    order_type: str = "MARKET"
    timestamp: str = ""
    metadata: Optional[dict] = None

    def to_record(self) -> dict:
        ts = self.timestamp or _utc_now_iso()
        side = _normalize_side(self.side)
        qty = max(_safe_float(self.qty), 0.0)
        expected = _safe_float(self.expected_price, 0.0)
        actual = _safe_float(self.actual_price, 0.0)
        metrics = compute_slippage_metrics(expected, actual, side)

        out = {
            "timestamp": ts,
            "symbol": str(self.symbol or "").upper(),
            "market": str(self.market or "auto").lower(),
            "side": side,
            "qty": round(qty, 8),
            "expected_price": round(expected, 8),
            "actual_price": round(actual, 8),
            "expected_notional": round(expected * qty, 8),
            "actual_notional": round(actual * qty, 8),
            "route": str(self.route or "MARKET").upper(),
            "order_type": str(self.order_type or "MARKET").upper(),
            **metrics,
            "metadata": self.metadata or {},
        }
        return out


class SlippageTracker:
    def __init__(
        self,
        supabase_client=_SUPABASE_AUTO,
        table_name: str = DEFAULT_TABLE,
        local_dir: Path = LOCAL_DIR,
    ):
        if supabase_client is _SUPABASE_AUTO:
            self.supabase = get_supabase()
        else:
            self.supabase = supabase_client
        self.table_name = table_name
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)

    def _local_file(self, timestamp_iso: str) -> Path:
        month = str(timestamp_iso or _utc_now_iso())[:7]
        return self.local_dir / f"{month}.jsonl"

    def _append_local(self, row: dict) -> None:
        path = self._local_file(str(row.get("timestamp") or _utc_now_iso()))
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def track_fill(self, fill: ExecutionFill, persist_db: bool = True) -> dict:
        row = fill.to_record()

        if persist_db and self.supabase is not None:
            try:
                self.supabase.table(self.table_name).insert(row).execute()
            except Exception as exc:
                log.warn("supabase execution_quality insert failed; fallback local", error=exc)
                self._append_local(row)
        else:
            self._append_local(row)

        return row

    def _query_db(self, start_iso: str, end_iso: str) -> List[dict]:
        if self.supabase is None:
            return []
        try:
            rows = (
                self.supabase.table(self.table_name)
                .select("*")
                .gte("timestamp", start_iso)
                .lt("timestamp", end_iso)
                .order("timestamp")
                .execute()
                .data
                or []
            )
            return rows
        except Exception as exc:
            log.warn("supabase execution_quality query failed", error=exc)
            return []

    def _query_local(self, start_iso: str, end_iso: str) -> List[dict]:
        rows: List[dict] = []
        for p in sorted(self.local_dir.glob("*.jsonl")):
            try:
                with p.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        ts = str(row.get("timestamp") or "")
                        if _in_range(ts, start_iso, end_iso):
                            rows.append(row)
            except Exception as exc:
                log.warn("local execution_quality read failed", path=str(p), error=exc)
        rows.sort(key=lambda x: str(x.get("timestamp") or ""))
        return rows

    def load_rows(self, start_iso: str, end_iso: str) -> List[dict]:
        rows = self._query_db(start_iso, end_iso)
        if rows:
            return rows
        return self._query_local(start_iso, end_iso)

    def monthly_report(self, year_month: Optional[str] = None) -> dict:
        ym = year_month or datetime.now().strftime("%Y-%m")
        start_iso, end_iso = _month_start_end(ym)
        rows = self.load_rows(start_iso, end_iso)

        if not rows:
            return {
                "year_month": ym,
                "trade_count": 0,
                "avg_abs_slippage_bps": 0.0,
                "avg_adverse_slippage_bps": 0.0,
                "worst_case": None,
                "route_stats": {},
            }

        abs_vals = [_safe_float(r.get("abs_slippage_bps"), 0.0) for r in rows]
        adverse_vals = [_safe_float(r.get("adverse_slippage_bps"), 0.0) for r in rows]

        worst_row = max(rows, key=lambda r: _safe_float(r.get("adverse_slippage_bps"), 0.0))

        route_stats: Dict[str, dict] = {}
        for r in rows:
            route = str(r.get("route") or "UNKNOWN").upper()
            route_stats.setdefault(route, {"count": 0, "avg_abs_slippage_bps": 0.0, "_vals": []})
            route_stats[route]["count"] += 1
            route_stats[route]["_vals"].append(_safe_float(r.get("abs_slippage_bps"), 0.0))

        for route, st in route_stats.items():
            vals = st.pop("_vals")
            st["avg_abs_slippage_bps"] = round(sum(vals) / len(vals), 6) if vals else 0.0

        return {
            "year_month": ym,
            "trade_count": len(rows),
            "avg_abs_slippage_bps": round(sum(abs_vals) / len(abs_vals), 6),
            "avg_adverse_slippage_bps": round(sum(adverse_vals) / len(adverse_vals), 6),
            "target_lt_10bps": (sum(abs_vals) / len(abs_vals)) < 10.0,
            "worst_case": {
                "timestamp": worst_row.get("timestamp"),
                "symbol": worst_row.get("symbol"),
                "side": worst_row.get("side"),
                "route": worst_row.get("route"),
                "adverse_slippage_bps": _safe_float(worst_row.get("adverse_slippage_bps"), 0.0),
            },
            "route_stats": route_stats,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Execution slippage tracker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_track = sub.add_parser("track", help="record one fill")
    p_track.add_argument("--symbol", required=True)
    p_track.add_argument("--side", required=True, choices=["buy", "sell"])
    p_track.add_argument("--qty", type=float, required=True)
    p_track.add_argument("--expected", type=float, required=True)
    p_track.add_argument("--actual", type=float, required=True)
    p_track.add_argument("--market", default="auto")
    p_track.add_argument("--route", default="MARKET")
    p_track.add_argument("--order-type", default="MARKET")

    p_report = sub.add_parser("report", help="monthly report")
    p_report.add_argument("--month", default=None, help="YYYY-MM")

    args = parser.parse_args()
    tracker = SlippageTracker()

    if args.cmd == "track":
        fill = ExecutionFill(
            symbol=args.symbol,
            side=args.side,
            qty=args.qty,
            expected_price=args.expected,
            actual_price=args.actual,
            market=args.market,
            route=args.route,
            order_type=args.order_type,
        )
        out = tracker.track_fill(fill, persist_db=True)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    out = tracker.monthly_report(year_month=args.month)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
