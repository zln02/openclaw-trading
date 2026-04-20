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

from common.config import (BRAIN_PATH, SIGNAL_IC_IR_MIN, SIGNAL_IC_MIN,
                           SIGNAL_IC_MIN_SAMPLES)
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import Priority, send_telegram
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
    "agent_team_confidence": ("agent_decisions", "confidence",    "pnl_pct",   True),
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


def compute_ic(signals: List[float], returns: List[float]) -> Optional[float]:
    """Spearman rank IC between *signals* and *returns*.

    Returns float in [-1, 1].
    # v6.2 A2: NULL/0 필터링 + 최소샘플 — n_valid < 10 시 None 반환
    Returns None if fewer than 10 valid non-zero pairs (was 5, stricter to avoid degenerate IC).
    """
    pairs = [(s, r) for s, r in zip(signals, returns)
             if s is not None and r is not None and s != 0 and r != 0]
    n_valid = len(pairs)
    if n_valid < 10:
        return None
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
    # v6.2 B8: 불편분산 (n-1)
    std = (sum((x - mean) ** 2 for x in ic_series) / (n - 1)) ** 0.5
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

        if signal_name == "agent_team_confidence":
            return self._load_agent_team_pairs(start_iso)

        try:
            # btc_position uses entry_price/entry_time, while trade tables use price/created_at.
            if table == "btc_position":
                select_cols = f"{sig_col},{pnl_col},entry_price,quantity,entry_time"
                time_col = "entry_time"
            else:
                select_cols = f"{sig_col},{pnl_col},price,quantity,created_at"
                time_col = "created_at"

            # v6.2 A2: NULL/0 필터링 + 최소샘플 — 동일값 IC 원인 방지
            q = (
                self.supabase.table(table)
                .select(select_cols)
                .gte(time_col, start_iso)
                .not_.is_(sig_col, "null")
                .neq(sig_col, 0)
            )
            # For btc_position, pnl might be stored in pnl_pct instead of pnl.
            # Do not hard-require pnl_col to be non-null at query time; filter in Python.
            if table != "btc_position":
                q = q.not_.is_(pnl_col, "null").neq(pnl_col, 0)

            rows = (q.execute().data or [])
        except Exception as exc:
            # Avoid structured logger JSON serialization errors for APIError objects.
            log.warning("signal data load failed", signal=signal_name, error=str(exc))
            return [], []

        signal_vals: List[float] = []
        pnl_vals: List[float] = []

        for r in rows:
            s = _safe_float(r.get(sig_col), None)
            p = _safe_float(r.get(pnl_col), None)
            if table == "btc_position" and p is None:
                # Fallback: some schemas store pnl only as pnl_pct
                p = _safe_float(r.get("pnl_pct"), None)
            if s is None or p is None:
                continue
            if not pnl_is_pct:
                # Normalize absolute PnL by cost basis if possible
                if table == "btc_position":
                    unit_price = _safe_float(r.get("entry_price"), 0.0)
                else:
                    unit_price = _safe_float(r.get("price"), 0.0)
                cost = unit_price * _safe_float(r.get("quantity"), 1.0)
                p = (p / cost * 100.0) if cost != 0 else p
            signal_vals.append(s)
            pnl_vals.append(p)

        return signal_vals, pnl_vals

    def _load_agent_team_pairs(self, start_iso: str) -> Tuple[List[float], List[float]]:
        try:
            decisions = (
                self.supabase.table("agent_decisions")
                .select("market,confidence,created_at")
                .gte("created_at", start_iso)
                .not_.is_("confidence", "null")
                .execute()
                .data
                or []
            )
            trades = (
                self.supabase.table("trade_executions")
                .select("created_at,pnl_pct")
                .gte("created_at", start_iso)
                .eq("trade_type", "SELL")
                .not_.is_("pnl_pct", "null")
                .execute()
                .data
                or []
            )
        except Exception as exc:
            log.warning("agent_team_confidence load failed", error=str(exc))
            return [], []

        trade_points: List[tuple[datetime, float]] = []
        for row in trades:
            created_at = str(row.get("created_at") or "").replace("Z", "+00:00")
            try:
                trade_points.append((datetime.fromisoformat(created_at), _safe_float(row.get("pnl_pct"), 0.0)))
            except Exception:
                continue

        signals: List[float] = []
        pnls: List[float] = []
        for row in decisions:
            created_at = str(row.get("created_at") or "").replace("Z", "+00:00")
            try:
                decision_ts = datetime.fromisoformat(created_at)
            except Exception:
                continue

            nearest_pnl = None
            nearest_gap = None
            for trade_ts, trade_pnl in trade_points:
                gap = abs((trade_ts - decision_ts).total_seconds())
                if gap > 1800:
                    continue
                if nearest_gap is None or gap < nearest_gap:
                    nearest_gap = gap
                    nearest_pnl = trade_pnl

            if nearest_pnl is None:
                continue

            signals.append(_safe_float(row.get("confidence"), 0.0))
            pnls.append(nearest_pnl)

        return signals, pnls

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
            if ic is not None:  # v6.2 A2: None(유효샘플 부족) 윈도우 skip
                series.append(ic)
        return series

    # ── Evaluation ──────────────────────────────────────────────────────

    def _permutation_test(
        self, signals: List[float], returns: List[float], n_perms: int = 500
    ) -> float:
        """순열 검정으로 IC 유의성 p-value 계산 (scipy 불필요).

        Returns:
            p-value in [0, 1].  낮을수록 IC가 통계적으로 유의함.
        """
        import random

        _raw_ic = compute_ic(signals, returns)
        if _raw_ic is None:
            return 1.0
        observed_ic = abs(_raw_ic)
        returns_copy = list(returns)
        count = 0
        for _ in range(n_perms):
            random.shuffle(returns_copy)
            perm_ic_val = compute_ic(signals, returns_copy)
            perm_ic = abs(perm_ic_val) if perm_ic_val is not None else 0.0
            if perm_ic >= observed_ic:
                count += 1
        return round(count / n_perms, 4)

    def evaluate_signal(self, signal_name: str) -> Dict[str, Any]:
        """Evaluate IC and IR for a single named signal."""
        sigs, rets = self._load_signal_pairs(signal_name)
        n = len(sigs)

        if n < SIGNAL_IC_MIN_SAMPLES:
            return {
                "signal": signal_name,
                "n": n,
                "ic": 0.0,
                "ir": 0.0,
                "p_value": 1.0,
                "significant": False,
                "status": "INSUFFICIENT_DATA",
                "active": False,
            }

        ic_raw = compute_ic(sigs, rets)
        # v6.2 A2: compute_ic가 None이면 유효 샘플 부족 — INSUFFICIENT_DATA 처리
        if ic_raw is None:
            return {
                "signal": signal_name,
                "n": n,
                "ic": 0.0,
                "ir": 0.0,
                "p_value": 1.0,
                "significant": False,
                "status": "INSUFFICIENT_DATA",
                "active": False,
            }
        ic = ic_raw
        ic_series = self._rolling_ic_series(sigs, rets)
        ir = compute_ir(ic_series) if len(ic_series) >= 3 else 0.0

        p_value = self._permutation_test(sigs, rets)
        significant = p_value < 0.05

        active = abs(ic) >= SIGNAL_IC_MIN and abs(ir) >= SIGNAL_IC_IR_MIN and significant
        status = "ACTIVE" if active else ("LOW_IC" if abs(ic) < SIGNAL_IC_MIN else "LOW_IR")

        if not significant:
            log.warning(
                "signal IC not statistically significant",
                signal=signal_name,
                ic=ic,
                p_value=p_value,
            )

        return {
            "signal": signal_name,
            "n": n,
            "ic": ic,
            "ir": ir,
            "p_value": p_value,
            "significant": significant,
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

    def export_weights(
        self,
        report: Dict[str, Any],
        *,
        cap_min: float = 0.02,
        cap_max: float = 0.30,  # v6.2 C4: 단일 신호 지배 방지 cap 하향
    ) -> Path:
        """Export IC/IR-derived signal weights to brain/signal-ic/weights.json.

        Design goals:
        - Use only *positive* predictive signals by default (ic <= 0 -> 0 weight).
        - Down-weight unstable signals (low IR).
        - Normalize to sum=1, with min/max caps, then renormalize.
        - If insufficient active signals, fall back to equal weights among positives.
        """
        EVAL_DIR.mkdir(parents=True, exist_ok=True)

        rows = report.get("signals") or []
        scored = []  # (name, raw_score)
        for r in rows:
            name = str(r.get("signal", "")).strip()
            ic = _safe_float(r.get("ic"), 0.0)
            ir = _safe_float(r.get("ir"), 0.0)
            n = int(_safe_float(r.get("n"), 0))
            if not name or n < SIGNAL_IC_MIN_SAMPLES:
                continue
            raw = max(0.0, ic) * max(0.0, ir)
            scored.append((name, raw))

        # Fallback: if everything is zero, try positive-IC only
        if not any(v > 0 for _, v in scored):
            scored = []
            for r in rows:
                name = str(r.get("signal", "")).strip()
                ic = _safe_float(r.get("ic"), 0.0)
                n = int(_safe_float(r.get("n"), 0))
                if not name or n < SIGNAL_IC_MIN_SAMPLES:
                    continue
                raw = max(0.0, ic)
                scored.append((name, raw))

        total = sum(v for _, v in scored if v > 0)
        fallback = False
        if total <= 0:
            # v6: equal-weight fallback — 데이터 충분한 신호에 균등 가중치
            eligible = [name for name, _ in scored if name]
            if not eligible:
                eligible = [name for name in _SIGNAL_SOURCES.keys()]
            if eligible:
                equal_w = round(1.0 / len(eligible), 6)
                weights = {k: equal_w for k in eligible}
                fallback = True
                log.warning(
                    "all IC/IR below threshold — using equal-weight fallback",
                    n_signals=len(eligible),
                )
            else:
                weights = {}
        else:
            weights = {k: v / total for k, v in scored if v > 0}

        # Apply caps then renormalize
        if weights:
            capped = {}
            for k, w in weights.items():
                capped[k] = max(cap_min, min(cap_max, float(w)))
            s = sum(capped.values())
            if s > 0:
                weights = {k: round(v / s, 6) for k, v in capped.items()}

        payload = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "lookback_days": report.get("lookback_days"),
            "window_days": report.get("window_days"),
            "method": "equal_weight_fallback" if fallback else "max(0,ic)*max(0,ir) -> normalize -> cap -> renormalize",
            "caps": {"min": cap_min, "max": cap_max},
            "weights": weights,
            "fallback": fallback,
        }

        path = EVAL_DIR / "weights.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("IC weights exported", path=str(path), count=len(weights))
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
            "📡 <b>신호 IC 평가 리포트</b>",
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
            send_telegram("\n".join(lines), priority=Priority.INFO)
        except Exception as exc:
            log.warning("IC report telegram send failed", error=exc)

    # ── Main entry ──────────────────────────────────────────────────────

    def run(self, notify: bool = True, save_db: bool = True) -> Dict[str, Any]:
        report = self.run_full_evaluation()
        path = self.save_report(report)
        weights_path = self.export_weights(report)
        if save_db:
            self.save_to_supabase(report)
        if notify:
            self.send_report(report)
        report["saved_path"] = str(path)
        report["weights_path"] = str(weights_path)
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
