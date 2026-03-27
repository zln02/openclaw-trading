#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.config import BRAIN_PATH
from common.logger import get_logger
from common.telegram import Priority, send_telegram
from ml_model import FEATURE_NAMES, extract_features, load_training_data, supabase

log = get_logger("ml_drift_monitor")

DRIFT_REPORT_PATH = BRAIN_PATH / "ml" / "drift_report.json"


def _psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if len(expected) < 20 or len(actual) < 10:
        return 0.0

    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.quantile(expected, quantiles)
    edges = np.unique(edges)
    if len(edges) < 3:
        return 0.0

    exp_hist, _ = np.histogram(expected, bins=edges)
    act_hist, _ = np.histogram(actual, bins=edges)

    exp_pct = np.clip(exp_hist / max(exp_hist.sum(), 1), 1e-6, None)
    act_pct = np.clip(act_hist / max(act_hist.sum(), 1), 1e-6, None)
    return float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))


def _ks_stat(expected: np.ndarray, actual: np.ndarray) -> dict:
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if len(expected) < 20 or len(actual) < 10:
        return {"statistic": 0.0, "pvalue": 1.0}
    try:
        from scipy.stats import ks_2samp

        stat = ks_2samp(expected, actual, alternative="two-sided", mode="auto")
        return {"statistic": float(stat.statistic), "pvalue": float(stat.pvalue)}
    except Exception:
        return {"statistic": 0.0, "pvalue": 1.0}


def load_recent_feature_matrix(lookback_days: int = 20) -> np.ndarray:
    if not supabase:
        return np.empty((0, len(FEATURE_NAMES)))

    since = (datetime.now(timezone.utc).date() - timedelta(days=max(lookback_days, 5))).isoformat()
    stocks = (
        supabase.table('top50_stocks')
        .select('stock_code')
        .execute()
        .data
        or []
    )

    all_X = []
    for s in stocks:
        code = s['stock_code']
        rows = (
            supabase.table('daily_ohlcv')
            .select('date,open_price,high_price,low_price,close_price,volume')
            .eq('stock_code', code)
            .gte('date', since)
            .order('date', desc=False)
            .execute()
            .data
            or []
        )
        if len(rows) < 5:
            continue

        full_rows = (
            supabase.table('daily_ohlcv')
            .select('date,open_price,high_price,low_price,close_price,volume')
            .eq('stock_code', code)
            .order('date', desc=True)
            .limit(160)
            .execute()
            .data
            or []
        )
        full_rows = list(reversed(full_rows))
        if len(full_rows) < 61:
            continue

        closes = [float(r['close_price']) for r in full_rows]
        volumes = [float(r.get('volume', 0)) for r in full_rows]
        highs = [float(r.get('high_price', r['close_price'])) for r in full_rows]
        lows = [float(r.get('low_price', r['close_price'])) for r in full_rows]
        dates = [r['date'] for r in full_rows]

        for idx, dt in enumerate(dates):
            if dt < since or idx < 60:
                continue
            try:
                feats = extract_features(
                    closes, volumes, highs, lows, idx,
                    stock_code=code,
                    as_of_date=dt,
                )
            except Exception:
                continue
            if feats is not None and len(feats) == len(FEATURE_NAMES):
                all_X.append(feats)

    if not all_X:
        return np.empty((0, len(FEATURE_NAMES)))
    return np.array(all_X, dtype=float)


def build_drift_report() -> dict:
    X_train, _ = load_training_data(target_days=3, target_return=0.02)
    X_recent = load_recent_feature_matrix(lookback_days=20)

    if X_train is None or len(X_train) == 0:
        return {"status": "NO_TRAIN_DATA", "generated_at": datetime.now(timezone.utc).isoformat() + "Z"}
    if len(X_recent) == 0:
        return {"status": "NO_RECENT_DATA", "generated_at": datetime.now(timezone.utc).isoformat() + "Z"}

    rows = []
    max_psi = 0.0
    high_psi = 0
    drifted_features = []

    for i, name in enumerate(FEATURE_NAMES):
        exp = X_train[:, i]
        act = X_recent[:, i]
        psi = _psi(exp, act)
        ks = _ks_stat(exp, act)
        level = "stable"
        if psi >= 0.25:
            level = "danger"
            high_psi += 1
        elif psi >= 0.10:
            level = "warning"
        if ks["pvalue"] < 0.01:
            drifted_features.append(name)
        max_psi = max(max_psi, psi)
        rows.append(
            {
                "feature": name,
                "psi": round(psi, 6),
                "ks_statistic": round(ks["statistic"], 6),
                "ks_pvalue": round(ks["pvalue"], 8),
                "train_mean": round(float(np.nanmean(exp)), 6),
                "recent_mean": round(float(np.nanmean(act)), 6),
                "level": level,
            }
        )

    rows.sort(key=lambda x: x["psi"], reverse=True)
    overall = "stable"
    action = "none"
    if max_psi >= 0.25:
        overall = "danger"
        action = "retrain"
    elif max_psi >= 0.10:
        overall = "warning"
        action = "alert"

    return {
        "horizon": "3d",
        "status": overall.upper(),
        "recommended_action": action,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "recent_samples": int(len(X_recent)),
        "training_samples": int(len(X_train)),
        "max_psi": round(max_psi, 6),
        "high_psi_count": int(high_psi),
        "ks_drift_features": drifted_features,
        "top_drift_features": rows[:15],
        "all_features": rows,
    }


def save_report(report: dict) -> Path:
    DRIFT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRIFT_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return DRIFT_REPORT_PATH


def maybe_notify(report: dict) -> None:
    status = report.get("status", "UNKNOWN")
    if status == "STABLE":
        return
    top = report.get("top_drift_features", [])[:5]
    summary = ", ".join(f"{r['feature']}({r['psi']:.3f})" for r in top)
    send_telegram(
        f"⚠️ ML Drift Monitor {status}\n"
        f"max PSI: {report.get('max_psi', 0):.3f}\n"
        f"action: {report.get('recommended_action')}\n"
        f"top: {summary}",
        priority=Priority.IMPORTANT if status == "WARNING" else Priority.URGENT,
    )


def maybe_retrain(report: dict, auto_retrain: bool) -> bool:
    if not auto_retrain or report.get("recommended_action") != "retrain":
        return False
    cmd = [str(Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python"), str(Path(__file__).resolve().parent / "ml_model.py"), "retrain", "3d", "50"]
    try:
        result = subprocess.run(cmd, check=False, cwd=str(Path(__file__).resolve().parent.parent))
        return result.returncode == 0
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="ML feature drift monitor")
    parser.add_argument("--auto-retrain", action="store_true")
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    report = build_drift_report()
    save_report(report)
    if not args.no_telegram:
        maybe_notify(report)
    retrained = maybe_retrain(report, auto_retrain=args.auto_retrain)
    report["auto_retrain_triggered"] = retrained
    save_report(report)
    log.info(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
