"""Portfolio optimizer (Phase 17).

Supported methods:
- mean_variance
- risk_parity
- black_litterman (lightweight blend)
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("portfolio_optimizer")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    clean = {str(k): max(_safe_float(v, 0.0), 0.0) for k, v in raw.items() if str(k)}
    total = sum(clean.values())
    if total <= 0:
        n = len(clean)
        return {k: (1.0 / n if n > 0 else 0.0) for k in clean}
    return {k: v / total for k, v in clean.items()}


def _bounded_class_weights(
    raw_class_weights: dict[str, float],
    class_min_weight: float,
    class_max_weight: float,
) -> dict[str, float]:
    classes = list(raw_class_weights.keys())
    if not classes:
        return {}

    low = max(_safe_float(class_min_weight, 0.1), 0.0)
    high = max(_safe_float(class_max_weight, 0.5), low)

    if low * len(classes) > 1.0:
        low = 1.0 / len(classes)
    if high * len(classes) < 1.0:
        high = 1.0

    base = _normalize_weights(raw_class_weights)
    fixed: dict[str, float] = {}
    free = set(classes)

    for _ in range(20):
        changed = False
        free_sum_raw = sum(base.get(c, 0.0) for c in free)
        rem = 1.0 - sum(fixed.values())
        if rem < 0:
            rem = 0.0

        trial: dict[str, float] = {}
        for c in free:
            if free_sum_raw > 0:
                trial[c] = rem * (base.get(c, 0.0) / free_sum_raw)
            else:
                trial[c] = rem / max(len(free), 1)

        newly_fixed: dict[str, float] = {}
        for c, w in trial.items():
            if w < low:
                newly_fixed[c] = low
                changed = True
            elif w > high:
                newly_fixed[c] = high
                changed = True

        if not changed:
            out = {**fixed, **trial}
            return _normalize_weights(out)

        for c, w in newly_fixed.items():
            fixed[c] = w
            free.discard(c)

        if not free:
            break

    out = {**fixed}
    rem = 1.0 - sum(out.values())
    if rem > 0 and classes:
        for c in classes:
            out[c] = out.get(c, 0.0) + rem / len(classes)
    return _normalize_weights(out)


def _allocate_with_cap(total_weight: float, raw_scores: dict[str, float], single_cap: float) -> dict[str, float]:
    assets = list(raw_scores.keys())
    if not assets:
        return {}

    total_weight = max(_safe_float(total_weight, 0.0), 0.0)
    if total_weight <= 0:
        return {a: 0.0 for a in assets}

    n = len(assets)
    cap = max(_safe_float(single_cap, 0.05), total_weight / max(n, 1))

    base = _normalize_weights(raw_scores)
    alloc = {a: min(base.get(a, 0.0) * total_weight, cap) for a in assets}

    for _ in range(20):
        used = sum(alloc.values())
        rem = total_weight - used
        if rem <= 1e-9:
            break

        free = [a for a in assets if alloc[a] + 1e-12 < cap]
        if not free:
            break

        free_raw_sum = sum(base.get(a, 0.0) for a in free)
        for a in free:
            if free_raw_sum > 0:
                add = rem * (base.get(a, 0.0) / free_raw_sum)
            else:
                add = rem / len(free)
            alloc[a] = min(cap, alloc[a] + add)

    return alloc


def _asset_vol(asset: str, cov: Mapping[str, Mapping[str, float]]) -> float:
    row = cov.get(asset) if isinstance(cov, Mapping) else None
    var = _safe_float((row or {}).get(asset), 0.0)
    return math.sqrt(var) if var > 0 else 1.0


@dataclass
class OptimizerConfig:
    class_min_weight: float = 0.10
    class_max_weight: float = 0.50
    single_name_max_weight: float = 0.05


class PortfolioOptimizer:
    def __init__(self, config: Optional[OptimizerConfig] = None):
        self.config = config or OptimizerConfig()

    def _raw_scores(
        self,
        expected_returns: Mapping[str, float],
        covariance: Mapping[str, Mapping[str, float]],
        method: str,
        views: Optional[Mapping[str, float]] = None,
    ) -> dict[str, float]:
        er = {str(k).upper(): _safe_float(v, 0.0) for k, v in expected_returns.items() if str(k)}
        cov = covariance or {}
        m = str(method or "mean_variance").lower()

        if m == "risk_parity":
            return {a: 1.0 / max(_asset_vol(a, cov), 1e-9) for a in er}

        if m == "black_litterman":
            v = {str(k).upper(): _safe_float(val, 0.0) for k, val in (views or {}).items()}
            # lightweight blend: 70% prior (ER), 30% views
            blended = {a: 0.7 * er.get(a, 0.0) + 0.3 * v.get(a, er.get(a, 0.0)) for a in er}
            return {a: max(blended.get(a, 0.0), 0.0) / max(_asset_vol(a, cov), 1e-9) for a in er}

        # mean_variance default
        return {a: max(er.get(a, 0.0), 0.0) / max(_asset_vol(a, cov), 1e-9) for a in er}

    def optimize(
        self,
        expected_returns: Mapping[str, float],
        covariance: Mapping[str, Mapping[str, float]],
        asset_class_map: Mapping[str, str],
        method: str = "mean_variance",
        views: Optional[Mapping[str, float]] = None,
    ) -> dict:
        if not expected_returns:
            return {
                "weights": {},
                "class_weights": {},
                "method": method,
                "constraints": asdict(self.config),
                "timestamp": _utc_now_iso(),
            }

        raw_asset = self._raw_scores(expected_returns, covariance, method=method, views=views)
        raw_asset = {a: v for a, v in raw_asset.items() if v > 0}
        if not raw_asset:
            raw_asset = {str(k).upper(): 1.0 for k in expected_returns.keys()}

        classes: dict[str, str] = {}
        for a in raw_asset:
            cls = str(asset_class_map.get(a) or "OTHER").upper()
            classes[a] = cls

        raw_class: dict[str, float] = {}
        for a, score in raw_asset.items():
            raw_class[classes[a]] = raw_class.get(classes[a], 0.0) + score

        class_w = _bounded_class_weights(
            raw_class,
            class_min_weight=self.config.class_min_weight,
            class_max_weight=self.config.class_max_weight,
        )

        by_class_assets: dict[str, dict[str, float]] = {}
        for a, score in raw_asset.items():
            cls = classes[a]
            by_class_assets.setdefault(cls, {})[a] = score

        weights: dict[str, float] = {}
        for cls, assets in by_class_assets.items():
            tw = class_w.get(cls, 0.0)
            alloc = _allocate_with_cap(
                total_weight=tw,
                raw_scores=assets,
                single_cap=self.config.single_name_max_weight,
            )
            weights.update(alloc)

        weights = _normalize_weights(weights)

        out_class_weights: dict[str, float] = {}
        for a, w in weights.items():
            out_class_weights[classes[a]] = out_class_weights.get(classes[a], 0.0) + w

        return {
            "weights": {k: round(v, 8) for k, v in sorted(weights.items())},
            "class_weights": {k: round(v, 8) for k, v in sorted(out_class_weights.items())},
            "method": method,
            "constraints": asdict(self.config),
            "timestamp": _utc_now_iso(),
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Portfolio optimizer")
    parser.add_argument("--method", default="mean_variance", choices=["mean_variance", "risk_parity", "black_litterman"])
    parser.add_argument("--input-file", default="", help="JSON with expected_returns/covariance/asset_class_map")
    args = parser.parse_args()

    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = {
            "expected_returns": {
                "BTC": 0.18,
                "A005930": 0.11,
                "A000660": 0.10,
                "AAPL": 0.12,
                "MSFT": 0.11,
            },
            "covariance": {
                "BTC": {"BTC": 0.16},
                "A005930": {"A005930": 0.05},
                "A000660": {"A000660": 0.06},
                "AAPL": {"AAPL": 0.04},
                "MSFT": {"MSFT": 0.03},
            },
            "asset_class_map": {
                "BTC": "CRYPTO",
                "A005930": "KR",
                "A000660": "KR",
                "AAPL": "US",
                "MSFT": "US",
            },
        }

    out = PortfolioOptimizer().optimize(
        expected_returns=payload.get("expected_returns") or {},
        covariance=payload.get("covariance") or {},
        asset_class_map=payload.get("asset_class_map") or {},
        method=args.method,
        views=payload.get("views") or {},
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
