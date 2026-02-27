"""Earnings surprise + PEAD model (Phase 16)."""
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def compute_sue(actual_eps: float, consensus_eps: float, surprise_std: float) -> float:
    actual = _safe_float(actual_eps, 0.0)
    est = _safe_float(consensus_eps, 0.0)
    std = max(abs(_safe_float(surprise_std, 0.0)), 1e-9)
    return round((actual - est) / std, 6)


@dataclass
class EarningsPrediction:
    symbol: str
    sue: float
    direction: str
    expected_drift_3d_pct: float
    confidence: float
    reason: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class EarningsSurpriseModel:
    def __init__(self):
        self.avg_pos_drift = 1.5
        self.avg_neg_drift = -1.2
        self.base_confidence = 55.0
        self.trained_samples = 0

    def fit(self, history_events: list[dict]) -> dict:
        if not history_events:
            self.trained_samples = 0
            return {"ok": False, "reason": "empty history"}

        pos: list[float] = []
        neg: list[float] = []

        for ev in history_events:
            if not isinstance(ev, dict):
                continue
            sue = _safe_float(ev.get("sue"), 0.0)
            drift = _safe_float(ev.get("drift_3d_pct"), 0.0)
            if sue >= 0:
                pos.append(drift)
            else:
                neg.append(drift)

        if pos:
            self.avg_pos_drift = sum(pos) / len(pos)
        if neg:
            self.avg_neg_drift = sum(neg) / len(neg)

        self.base_confidence = 55.0 + min(len(history_events), 40) * 0.5
        self.trained_samples = len(history_events)

        return {
            "ok": True,
            "samples": self.trained_samples,
            "avg_pos_drift": round(self.avg_pos_drift, 6),
            "avg_neg_drift": round(self.avg_neg_drift, 6),
            "base_confidence": round(self.base_confidence, 2),
        }

    def predict(
        self,
        symbol: str,
        actual_eps: float,
        consensus_eps: float,
        surprise_std: float,
    ) -> dict:
        sue = compute_sue(actual_eps, consensus_eps, surprise_std)

        if sue >= 0.5:
            direction = "BULLISH"
            expected_drift = self.avg_pos_drift * min(1.8, 1.0 + sue * 0.2)
            reason = "positive earnings surprise"
        elif sue <= -0.5:
            direction = "BEARISH"
            expected_drift = self.avg_neg_drift * min(1.8, 1.0 + abs(sue) * 0.2)
            reason = "negative earnings surprise"
        else:
            direction = "NEUTRAL"
            expected_drift = 0.0
            reason = "small surprise"

        confidence = self.base_confidence + min(abs(sue) * 8.0, 35.0)
        confidence = max(0.0, min(confidence, 99.0))

        out = EarningsPrediction(
            symbol=str(symbol or "").upper(),
            sue=round(sue, 6),
            direction=direction,
            expected_drift_3d_pct=round(expected_drift, 6),
            confidence=round(confidence, 2),
            reason=reason,
            timestamp=_utc_now_iso(),
        )
        return out.to_dict()

    def fit_from_raw_events(self, history_events: list[dict]) -> dict:
        rows: list[dict] = []
        surprises: list[float] = []

        for ev in history_events:
            if not isinstance(ev, dict):
                continue
            actual = _safe_float(ev.get("actual_eps"), 0.0)
            consensus = _safe_float(ev.get("consensus_eps"), 0.0)
            surprises.append(actual - consensus)

        if len(surprises) >= 2:
            std = statistics.pstdev(surprises)
        else:
            std = max(abs(surprises[0]), 0.01) if surprises else 0.01

        for ev in history_events:
            if not isinstance(ev, dict):
                continue
            sue = compute_sue(
                actual_eps=ev.get("actual_eps"),
                consensus_eps=ev.get("consensus_eps"),
                surprise_std=std,
            )
            rows.append({
                "sue": sue,
                "drift_3d_pct": _safe_float(ev.get("drift_3d_pct"), 0.0),
            })

        meta = self.fit(rows)
        meta["derived_surprise_std"] = round(std, 6)
        return meta


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Earnings surprise model")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--actual", type=float, required=True)
    parser.add_argument("--consensus", type=float, required=True)
    parser.add_argument("--std", type=float, default=0.1, help="surprise std")
    args = parser.parse_args()

    model = EarningsSurpriseModel()
    out = model.predict(
        symbol=args.symbol,
        actual_eps=args.actual,
        consensus_eps=args.consensus,
        surprise_std=args.std,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
