"""Signal IC (Information Coefficient) measurement system (Phase 13).

Computes per-signal predictive quality metrics:
  IC  = Spearman rank correlation between signal at entry time and realized PnL %
  IR  = IC.mean() / IC.std()  (annualised if needed)

Signals evaluated (wherever data is available in Supabase):
  ml_score        : XGBoost ML model buy-probability at entry
  btc_composite   : BTC composite onchain/tech score at entry
  rsi_signal      : RSI at entry (normalized 0-100)
  fg_index        : Fear & Greed index at entry
  funding_rate    : BTC perpetual funding rate at entry
  news_sentiment  : aggregated news sentiment score at entry
  composite_score : generic composite score stored per trade

Thresholds (from common.config):
  SIGNAL_IC_MIN    = 0.02   → IC below this → signal unreliable
  SIGNAL_IC_IR_MIN = 0.3    → IR below this → signal unstable
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common.config import BRAIN_PATH, SIGNAL_IC_MIN, SIGNAL_IC_IR_MIN
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import send_telegram
from common.utils import safe_float as _safe_float

load_env()
log = get_logger("signal_evaluator")

EVAL_DIR = BRAIN_PATH / "signal-ic"

# ── Signal column mapping per Supabase table ───────────────────────────────
# Each entry: (table_name, signal_col, pnl_col, pnl_is_pct)
#   pnl_is_pct=True  → value is already a percentage (e.g. 5.2 means +5.2%)
#   pnl_is_pct=False → absolute PnL; we'll normalize by cost if possible
_SIGNAL_SOURCES: Dict[str, Tuple[str, str, str, bool]] = {
    "ml_score":        ("trade_executions",    "ml_score",        "pnl_pct",   True),
    "composite_score": ("trade_executions",    "composite_score", "pnl_pct",   True),
    "rsi_signal":      ("trade_executions",    "rsi",             "pnl_pct",   True),
    "news_sentiment":  ("trade_executions",    "news_sentiment",  "pnl_pct",   True),
    "btc_composite":   ("btc_position",        "composite_score", "pnl",       False),
    "fg_index":        ("btc_position",        "fg_value",        "pnl",       False),
    "funding_rate":    ("btc_position",        "funding_rate",    "pnl",       False),
}


# ── Pure-math IC/IR helpers ────────────────────────────────────────────────

def _rank(values: List[float]) -> List[float]:
    """Return rank vector (1-based) for a list of floats."""
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    for rank, (idx, _) in enumerate(indexed, 1):
        ranks[idx] = float(rank)
    return ranks


def compute_ic(signals: List[float], returns: List[float]) -> float:
    """Spearman rank IC between *signals* and *returns*.

    Returns float in [-1, 1].  Returns 0.0 if fewer than 5 valid pairs.
    """
    pairs = [(s, r) for s, r in zip(signals, returns) if s is not None and r is not None]
    if len(pairs) < 5:
        return 0.0
    sx, sy = zip(*pairs)
    rx = _rank(list(sx))
    ry = _rank(list(sy))
    n = len(rx)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry)) / n
    std_x = (sum((a - mean_x) ** 2 for a in rx) / n) ** 0.5
    std_y = (sum((b - mean_y) ** 2 for b in ry) / n) ** 0.5
    if std_x == 0 or std_y == 0:
        return 0.0
    return round(cov / (std_x * std_y), 6)


def compute_ir(ic_series: List[float]) -> float:
    """IC Information Ratio = mean(IC) / std(IC).

    Returns 0.0 if fewer than 3 observations or std == 0.
    """
    if len(ic_series) < 3:
        return 0.0
    n = len(ic_series)
    mean = sum(ic_series) / n
    std = (sum((x - mean) ** 2 for x in ic_series) / n) ** 0.5
    if std == 0:
        return 0.0
    return round(mean / std, 4)


# ── SignalEvaluator ────────────────────────────────────────────────────────

class SignalEvaluator:
    def __init__(self, supabase_client=None, lookback_days: int = 90, window_days: int = 14):
        """
        Args:
            lookback_days: how far back to pull trade records from Supabase.
            window_days:   rolling window size for IC-series (used to compute IR).
        """
        self.supabase = supabase_client or get_supabase()
        self.lookback_days = max(lookback_days, 7)
        self.window_days = max(window_days, 3)

    # ── Data loading ────────────────────────────────────────────────────

    def _load_signal_pairs(
        self,
        signal_name: str,
    ) -> Tuple[List[float], List[float]]:
        """Return (signal_values, pnl_values) for a named signal.

        Falls back to ([], []) if signal column is missing or table empty.
        """
        if signal_name not in _SIGNAL_SOURCES:
            return [], []

        table, sig_col, pnl_col, pnl_is_pct = _SIGNAL_SOURCES[signal_name]
        start_iso = (
            datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        ).date().isoformat()

        if not self.supabase:
            return [], []

        try:
            rows = (
                self.supabase.table(table)
                .select(f"{sig_col},{pnl_col},price,quantity")
                .gte("created_at", start_iso)
                .not_.is_(sig_col, "null")
                .not_.is_(pnl_col, "null")
                .execute()
                .data
                or []
            )
        except Exception as exc:
            log.warning("signal data load failed", signal=signal_name, error=exc)
            return [], []

        signal_vals: List[float] = []
        pnl_vals: List[float] = []

        for r in rows:
            s = _safe_float(r.get(sig_col), None)
            p = _safe_float(r.get(pnl_col), None)
            if s is None or p is None:
                continue
            if not pnl_is_pct:
                # Normalize absolute PnL by cost basis if possible
                cost = _safe_float(r.get("price"), 0.0) * _safe_float(r.get("quantity"), 1.0)
                p = (p / cost * 100.0) if cost != 0 else p
            signal_vals.append(s)
            pnl_vals.append(p)

        return signal_vals, pnl_vals

    def _rolling_ic_series(
        self, signal_vals: List[float], pnl_vals: List[float]
    ) -> List[float]:
        """Compute IC in rolling windows of `window_days` samples.

        Returns a list of per-window IC values.
        """
        w = self.window_days
        series: List[float] = []
        for start in range(0, len(signal_vals) - w + 1, max(1, w // 2)):
            end = start + w
            ic = compute_ic(signal_vals[start:end], pnl_vals[start:end])
            series.append(ic)
        return series

    # ── Evaluation ──────────────────────────────────────────────────────

    def evaluate_signal(self, signal_name: str) -> Dict[str, Any]:
        """Evaluate IC and IR for a single named signal."""
        sigs, rets = self._load_signal_pairs(signal_name)
        n = len(sigs)

        if n < 5:
            return {
                "signal": signal_name,
                "n": n,
                "ic": 0.0,
                "ir": 0.0,
                "status": "INSUFFICIENT_DATA",
                "active": False,
            }

        ic = compute_ic(sigs, rets)
        ic_series = self._rolling_ic_series(sigs, rets)
        ir = compute_ir(ic_series) if len(ic_series) >= 3 else 0.0

        active = abs(ic) >= SIGNAL_IC_MIN and abs(ir) >= SIGNAL_IC_IR_MIN
        status = "ACTIVE" if active else ("LOW_IC" if abs(ic) < SIGNAL_IC_MIN else "LOW_IR")

        return {
            "signal": signal_name,
            "n": n,
            "ic": ic,
            "ir": ir,
            "ic_series_len": len(ic_series),
            "status": status,
            "active": active,
        }

    def run_full_evaluation(self) -> Dict[str, Any]:
        """Evaluate all registered signals and produce a consolidated report."""
        results: List[Dict[str, Any]] = []
        for sig_name in _SIGNAL_SOURCES:
            try:
                r = self.evaluate_signal(sig_name)
                results.append(r)
                log.info(
                    "signal evaluated",
                    signal=sig_name,
                    n=r["n"],
                    ic=r["ic"],
                    ir=r["ir"],
                    status=r["status"],
                )
            except Exception as exc:
                log.warning("signal evaluation failed", signal=sig_name, error=exc)
                results.append({"signal": sig_name, "n": 0, "ic": 0.0, "ir": 0.0,
                                 "status": "ERROR", "active": False})

        active = [r for r in results if r.get("active")]
        inactive = [r for r in results if not r.get("active")]

        report: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lookback_days": self.lookback_days,
            "window_days": self.window_days,
            "thresholds": {"ic_min": SIGNAL_IC_MIN, "ir_min": SIGNAL_IC_IR_MIN},
            "signals": results,
            "summary": {
                "total": len(results),
                "active": len(active),
                "inactive": len(inactive),
                "active_names": [r["signal"] for r in active],
            },
        }
        return report

    # ── Persistence ─────────────────────────────────────────────────────

    def save_report(self, report: Dict[str, Any]) -> Path:
        """Save evaluation report to brain/signal-ic/YYYY-MM-DD.json."""
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).date().isoformat()
        path = EVAL_DIR / f"{today}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("IC report saved", path=str(path))
        return path

    def save_to_supabase(self, report: Dict[str, Any]) -> None:
        """Upsert per-signal IC results into signal_ic_history table (if exists)."""
        if not self.supabase:
            return
        today = datetime.now(timezone.utc).date().isoformat()
        rows = [
            {
                "date": today,
                "signal": r["signal"],
                "n": r["n"],
                "ic": r["ic"],
                "ir": r["ir"],
                "status": r["status"],
                "active": r["active"],
            }
            for r in report.get("signals", [])
        ]
        try:
            self.supabase.table("signal_ic_history").upsert(rows, on_conflict="date,signal").execute()
            log.info("IC results saved to Supabase", count=len(rows))
        except Exception as exc:
            log.warning("supabase IC upsert failed", error=exc)

    def send_report(self, report: Dict[str, Any]) -> None:
        """Format and send signal IC summary to Telegram."""
        summary = report.get("summary", {})
        lines = [
            f"📡 <b>신호 IC 평가 리포트</b>",
            f"기간: {report.get('lookback_days', '?')}일 | 임계: IC≥{SIGNAL_IC_MIN} IR≥{SIGNAL_IC_IR_MIN}",
            f"활성: {summary.get('active', 0)}/{summary.get('total', 0)}개",
            "",
        ]
        for r in report.get("signals", []):
            icon = "✅" if r.get("active") else "⚠️"
            lines.append(
                f"{icon} {r['signal']}: IC={r['ic']:+.3f} IR={r['ir']:+.3f} "
                f"n={r['n']} [{r['status']}]"
            )

        inactive_names = [r["signal"] for r in report.get("signals", []) if not r.get("active")]
        if inactive_names:
            lines.append(f"\n비활성 신호: {', '.join(inactive_names)}")

        try:
            send_telegram("\n".join(lines))
        except Exception as exc:
            log.warning("IC report telegram send failed", error=exc)

    # ── Main entry ──────────────────────────────────────────────────────

    def run(self, notify: bool = True, save_db: bool = True) -> Dict[str, Any]:
        report = self.run_full_evaluation()
        path = self.save_report(report)
        if save_db:
            self.save_to_supabase(report)
        if notify:
            self.send_report(report)
        report["saved_path"] = str(path)
        return report


# ── CLI ────────────────────────────────────────────────────────────────────

def _cli() -> int:
    p = argparse.ArgumentParser(description="Signal IC/IR evaluator")
    p.add_argument("--lookback", type=int, default=90, help="days of history to analyse")
    p.add_argument("--window", type=int, default=14, help="rolling IC window size (samples)")
    p.add_argument("--signal", default=None, help="evaluate a single named signal")
    p.add_argument("--no-notify", action="store_true", help="skip Telegram notification")
    p.add_argument("--no-db", action="store_true", help="skip Supabase upsert")
    args = p.parse_args()

    evaluator = SignalEvaluator(lookback_days=args.lookback, window_days=args.window)

    if args.signal:
        out = evaluator.evaluate_signal(args.signal)
    else:
        out = evaluator.run(notify=not args.no_notify, save_db=not args.no_db)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
