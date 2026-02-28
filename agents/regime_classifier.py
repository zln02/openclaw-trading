"""Market regime classifier (Phase 12).

Regimes:
- RISK_ON
- RISK_OFF
- TRANSITION
- CRISIS

Approach:
- Feature extraction from market data (SPY, VIX, credit proxies)
- Optional XGBoost classifier (if trained model exists)
- Rule-based fallback always available
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from common.cache import get_cached, set_cached
from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.retry import retry_call
from common.utils import safe_float as _safe_float

load_env()
log = get_logger("regime_classifier")

MODEL_DIR = BRAIN_PATH / "regime-model"
MODEL_PATH = MODEL_DIR / "xgb_regime_model.json"

REGIME_PRESETS = {
    "RISK_ON": {
        "buy_threshold_adj": -3,
        "max_positions": 7,
        "invest_ratio_scale": 1.10,
        "stop_loss_scale": 1.00,
    },
    "RISK_OFF": {
        "buy_threshold_adj": +8,
        "max_positions": 3,
        "invest_ratio_scale": 0.70,
        "stop_loss_scale": 0.90,
    },
    "TRANSITION": {
        "buy_threshold_adj": +2,
        "max_positions": 5,
        "invest_ratio_scale": 0.90,
        "stop_loss_scale": 0.95,
    },
    "CRISIS": {
        "buy_threshold_adj": +15,
        "max_positions": 1,
        "invest_ratio_scale": 0.35,
        "stop_loss_scale": 0.80,
    },
}


def _to_iso_day(value: str | date | datetime | None = None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return datetime.now().date().isoformat()
    return str(value).strip()[:10]


def _parse_day(value: str | date | datetime | None = None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return datetime.now().date()
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _std(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (n - 1)
    return float(math.sqrt(var))


def _skew(values: Sequence[float]) -> float:
    n = len(values)
    if n < 3:
        return 0.0
    m = _mean(values)
    s = _std(values)
    if s <= 0:
        return 0.0
    return (sum(((x - m) / s) ** 3 for x in values) * n / ((n - 1) * (n - 2)))


def _kurtosis(values: Sequence[float]) -> float:
    n = len(values)
    if n < 4:
        return 0.0
    m = _mean(values)
    s = _std(values)
    if s <= 0:
        return 0.0
    num = sum(((x - m) / s) ** 4 for x in values)
    return (n * (n + 1) * num / ((n - 1) * (n - 2) * (n - 3))) - (3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))


def _corr(x: Sequence[float], y: Sequence[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    xs = [float(v) for v in x[-n:]]
    ys = [float(v) for v in y[-n:]]
    mx = _mean(xs)
    my = _mean(ys)
    vx = sum((v - mx) ** 2 for v in xs)
    vy = sum((v - my) ** 2 for v in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    return float(cov / math.sqrt(vx * vy))


def _returns(close: Sequence[float]) -> List[float]:
    arr = [float(x) for x in close if _safe_float(x, 0.0) > 0]
    out = []
    for i in range(1, len(arr)):
        prev = arr[i - 1]
        cur = arr[i]
        if prev > 0:
            out.append(cur / prev - 1.0)
    return out


def _fetch_close(
    symbol: str,
    start_iso: str | None = None,
    end_iso: str | None = None,
    period: str = "2y",
) -> List[float]:
    try:
        import yfinance as yf

        kwargs = {"interval": "1d"}
        if start_iso and end_iso:
            kwargs.update({"start": start_iso, "end": end_iso})
        else:
            kwargs.update({"period": period})

        hist = retry_call(
            yf.Ticker(symbol).history,
            kwargs=kwargs,
            max_attempts=2,
            base_delay=1.0,
            default=None,
        )

        # Fallback if the requested date range does not return enough rows.
        if (hist is None or hist.empty) and (start_iso and end_iso):
            hist = retry_call(
                yf.Ticker(symbol).history,
                kwargs={"period": period, "interval": "1d"},
                max_attempts=2,
                base_delay=1.0,
                default=None,
            )

        if hist is None or hist.empty or "Close" not in hist:
            return []
        return [float(v) for v in list(hist["Close"]) if _safe_float(v, 0.0) > 0]
    except Exception as exc:
        log.warn("fetch close failed", symbol=symbol, error=exc)
        return []


@dataclass
class RegimeResult:
    regime: str
    confidence: float
    features: dict
    source: str
    preset: dict

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "confidence": round(self.confidence, 6),
            "features": self.features,
            "source": self.source,
            "preset": self.preset,
        }


class RegimeClassifier:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = Path(model_path)
        self._model = None

    def get_features(self, as_of: str | date | datetime | None = None) -> dict:
        as_of_iso = _to_iso_day(as_of)
        cache_key = f"regime:features:{as_of_iso}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached

        as_of_day = _parse_day(as_of_iso)
        start_iso = (as_of_day - timedelta(days=900)).isoformat()
        end_iso = (as_of_day + timedelta(days=1)).isoformat()

        spy = _fetch_close("SPY", start_iso=start_iso, end_iso=end_iso, period="5y")
        qqq = _fetch_close("QQQ", start_iso=start_iso, end_iso=end_iso, period="5y")
        vix = _fetch_close("^VIX", start_iso=start_iso, end_iso=end_iso, period="5y")
        hyg = _fetch_close("HYG", start_iso=start_iso, end_iso=end_iso, period="5y")
        lqd = _fetch_close("LQD", start_iso=start_iso, end_iso=end_iso, period="5y")

        spy_ret = _returns(spy)
        qqq_ret = _returns(qqq)

        def _ret(arr: List[float], n: int) -> float:
            if len(arr) <= n:
                return 0.0
            p0 = arr[-1 - n]
            p1 = arr[-1]
            if p0 <= 0:
                return 0.0
            return p1 / p0 - 1.0

        credit_spread = 0.0
        if hyg and lqd:
            nh = hyg[-1] / hyg[-21] - 1.0 if len(hyg) > 21 and hyg[-21] > 0 else 0.0
            nl = lqd[-1] / lqd[-21] - 1.0 if len(lqd) > 21 and lqd[-21] > 0 else 0.0
            credit_spread = nh - nl

        corr_20 = _corr(spy_ret[-20:], qqq_ret[-20:]) if spy_ret and qqq_ret else 0.0
        corr_60 = _corr(spy_ret[-60:], qqq_ret[-60:]) if spy_ret and qqq_ret else 0.0

        feat = {
            "spy_ret_5d": round(_ret(spy, 5), 6),
            "spy_ret_20d": round(_ret(spy, 20), 6),
            "spy_vol_20d": round(_std(spy_ret[-20:]), 6),
            "vix_level": round(vix[-1], 6) if vix else 20.0,
            "vix_ret_5d": round(_ret(vix, 5), 6),
            "vix_term_proxy": round(_mean(vix[-5:]) - _mean(vix[-20:]), 6) if len(vix) >= 20 else 0.0,
            "ret_skew_60d": round(_skew(spy_ret[-60:]), 6),
            "ret_kurt_60d": round(_kurtosis(spy_ret[-60:]), 6),
            "credit_spread_proxy": round(credit_spread, 6),
            "corr_shift_20_60": round(corr_20 - corr_60, 6),
        }
        set_cached(cache_key, feat, ttl=900)
        return feat

    def classify_rule(self, features: dict) -> RegimeResult:
        vix = _safe_float(features.get("vix_level"), 20.0)
        spy_20d = _safe_float(features.get("spy_ret_20d"), 0.0)
        vol_20d = _safe_float(features.get("spy_vol_20d"), 0.0)
        credit = _safe_float(features.get("credit_spread_proxy"), 0.0)
        corr_shift = _safe_float(features.get("corr_shift_20_60"), 0.0)

        if vix >= 35 or (spy_20d <= -0.12 and vol_20d > 0.03):
            regime = "CRISIS"
            conf = 0.85
        elif vix >= 25 or spy_20d <= -0.05 or credit <= -0.03:
            regime = "RISK_OFF"
            conf = 0.72
        elif abs(spy_20d) < 0.03 or abs(corr_shift) > 0.15:
            regime = "TRANSITION"
            conf = 0.62
        else:
            regime = "RISK_ON"
            conf = 0.75

        return RegimeResult(
            regime=regime,
            confidence=conf,
            features=features,
            source="RULE",
            preset=REGIME_PRESETS.get(regime, {}),
        )

    def _load_model(self):
        if self._model is not None:
            return self._model
        if not self.model_path.exists():
            return None
        try:
            import xgboost as xgb

            model = xgb.XGBClassifier()
            model.load_model(str(self.model_path))
            self._model = model
            return model
        except Exception as exc:
            log.warn("regime model load failed", path=str(self.model_path), error=exc)
            return None

    def classify(self, as_of: str | date | datetime | None = None, use_model: bool = True) -> dict:
        features = self.get_features(as_of=as_of)

        if use_model:
            model = self._load_model()
            if model is not None:
                try:
                    labels = ["RISK_ON", "RISK_OFF", "TRANSITION", "CRISIS"]
                    order = [
                        "spy_ret_5d",
                        "spy_ret_20d",
                        "spy_vol_20d",
                        "vix_level",
                        "vix_ret_5d",
                        "vix_term_proxy",
                        "ret_skew_60d",
                        "ret_kurt_60d",
                        "credit_spread_proxy",
                        "corr_shift_20_60",
                    ]
                    import numpy as np

                    X = np.array([[float(features.get(k, 0.0)) for k in order]], dtype=float)
                    probs = model.predict_proba(X)[0]
                    idx = int(max(range(len(probs)), key=lambda i: probs[i]))
                    regime = labels[idx] if idx < len(labels) else "TRANSITION"
                    conf = float(probs[idx]) if idx < len(probs) else 0.5
                    return RegimeResult(
                        regime=regime,
                        confidence=conf,
                        features=features,
                        source="XGBOOST",
                        preset=REGIME_PRESETS.get(regime, {}),
                    ).to_dict()
                except Exception as exc:
                    log.warn("regime model predict failed; fallback rule", error=exc)

        return self.classify_rule(features).to_dict()

    def train_from_rule_labels(self, years: int = 5) -> dict:
        """Bootstrap XGBoost model using rule-derived pseudo labels over history."""
        try:
            import numpy as np
            import xgboost as xgb
        except Exception as exc:
            return {"ok": False, "error": f"xgboost unavailable: {exc}"}

        # build monthly samples
        end = datetime.now().date()
        start = end - timedelta(days=max(years, 1) * 365)

        rows = []
        labels = []
        d = date(start.year, start.month, 1)
        while d <= end:
            try:
                feat = self.get_features(as_of=d.isoformat())
                rule = self.classify_rule(feat)
                rows.append(
                    [
                        _safe_float(feat.get("spy_ret_5d")),
                        _safe_float(feat.get("spy_ret_20d")),
                        _safe_float(feat.get("spy_vol_20d")),
                        _safe_float(feat.get("vix_level")),
                        _safe_float(feat.get("vix_ret_5d")),
                        _safe_float(feat.get("vix_term_proxy")),
                        _safe_float(feat.get("ret_skew_60d")),
                        _safe_float(feat.get("ret_kurt_60d")),
                        _safe_float(feat.get("credit_spread_proxy")),
                        _safe_float(feat.get("corr_shift_20_60")),
                    ]
                )
                labels.append({"RISK_ON": 0, "RISK_OFF": 1, "TRANSITION": 2, "CRISIS": 3}[rule.regime])
            except Exception:
                pass

            # next month
            if d.month == 12:
                d = date(d.year + 1, 1, 1)
            else:
                d = date(d.year, d.month + 1, 1)

        if len(rows) < 24:
            return {"ok": False, "error": f"not enough samples: {len(rows)}"}

        X = np.array(rows, dtype=float)
        y = np.array(labels, dtype=int)

        model = xgb.XGBClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob",
            num_class=4,
            random_state=42,
        )
        model.fit(X, y)

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        model.save_model(str(self.model_path))
        self._model = model

        return {"ok": True, "samples": int(len(rows)), "model_path": str(self.model_path)}

    def get_preset(self, regime: str) -> dict:
        return REGIME_PRESETS.get(str(regime or "").upper(), {})


def _cli() -> int:
    p = argparse.ArgumentParser(description="Market regime classifier")
    p.add_argument("--train", action="store_true", help="train xgboost model from rule labels")
    p.add_argument("--years", type=int, default=5, help="years for bootstrap training")
    p.add_argument("--as-of", default=None, help="YYYY-MM-DD")
    p.add_argument("--no-model", action="store_true", help="rule-only prediction")
    args = p.parse_args()

    clf = RegimeClassifier()
    if args.train:
        out = clf.train_from_rule_labels(years=args.years)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("ok") else 1

    out = clf.classify(as_of=args.as_of, use_model=not args.no_model)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
