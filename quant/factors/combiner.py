"""Factor combination optimizer (Phase 10).

Supports:
- IC-weighted combination
- Ridge/Lasso based fitting (optional)
- Overfit guards: L2 shrinkage + per-factor max weight cap
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("factor_combiner")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_with_cap(weights: Dict[str, float], max_weight: float = 0.30) -> Dict[str, float]:
    if not weights:
        return {}

    # keep non-negative weights only
    w = {k: max(_safe_float(v), 0.0) for k, v in weights.items()}
    total = sum(w.values())
    if total <= 0:
        n = len(w)
        return {k: 1.0 / n for k in w}

    # initial normalize
    w = {k: v / total for k, v in w.items()}

    # iterative cap-and-redistribute
    remaining = set(w.keys())
    fixed: Dict[str, float] = {}
    while remaining:
        subtotal = sum(w[k] for k in remaining)
        if subtotal <= 0:
            break

        updated = False
        for k in list(remaining):
            scaled = w[k] / subtotal * (1.0 - sum(fixed.values()))
            if scaled > max_weight:
                fixed[k] = max_weight
                remaining.remove(k)
                updated = True

        if not updated:
            left = 1.0 - sum(fixed.values())
            if left < 0:
                left = 0.0
            sub = sum(w[k] for k in remaining)
            if sub <= 0:
                break
            for k in remaining:
                fixed[k] = w[k] / sub * left
            remaining.clear()

    # final normalize safeguard
    final_sum = sum(fixed.values())
    if final_sum > 0:
        fixed = {k: v / final_sum for k, v in fixed.items()}
    return fixed


@dataclass
class CombineConfig:
    method: str = "ic_weighted"  # ic_weighted | ridge | lasso
    l2_alpha: float = 1.0
    max_weight: float = 0.30


class FactorCombiner:
    def __init__(self, config: Optional[CombineConfig] = None):
        self.config = config or CombineConfig()

    def fit(
        self,
        factor_matrix: List[Dict[str, float]],
        targets: List[float],
        factor_names: Optional[Iterable[str]] = None,
        ic_stats: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, float]:
        names = list(factor_names) if factor_names is not None else self._collect_names(factor_matrix)
        if not names:
            return {}

        method = (self.config.method or "ic_weighted").lower().strip()
        if method == "ridge":
            w = self._fit_ridge(factor_matrix, targets, names)
        elif method == "lasso":
            w = self._fit_lasso(factor_matrix, targets, names)
        else:
            w = self._fit_ic_weighted(names, ic_stats or {})

        return _normalize_with_cap(w, max_weight=self.config.max_weight)

    def score(self, factor_values: Dict[str, float], weights: Dict[str, float]) -> float:
        if not factor_values or not weights:
            return 0.0
        s = 0.0
        for k, w in weights.items():
            s += _safe_float(factor_values.get(k), 0.0) * _safe_float(w, 0.0)
        return s

    def _collect_names(self, factor_matrix: List[Dict[str, float]]) -> List[str]:
        bag = set()
        for row in factor_matrix:
            for k in row.keys():
                bag.add(str(k))
        return sorted(bag)

    def _fit_ic_weighted(self, names: List[str], ic_stats: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        for name in names:
            stat = ic_stats.get(name) or {}
            ic_mean = _safe_float(stat.get("ic_mean"), 0.0)
            ic_ir = _safe_float(stat.get("ic_ir"), 0.0)
            if ic_mean <= 0 or ic_ir <= 0:
                continue
            # roadmap guard: IC > 0.03 and IC IR > 0.5 preferred
            bonus = 1.2 if (ic_mean > 0.03 and ic_ir > 0.5) else 1.0
            weights[name] = ic_mean * ic_ir * bonus

        if not weights:
            # equal fallback
            weights = {n: 1.0 for n in names}
        return weights

    def _fit_ridge(self, factor_matrix: List[Dict[str, float]], targets: List[float], names: List[str]) -> Dict[str, float]:
        if not factor_matrix or not targets or len(factor_matrix) != len(targets):
            return {n: 1.0 for n in names}

        try:
            import numpy as np
            from sklearn.linear_model import Ridge

            X = np.array([[float(row.get(n, 0.0)) for n in names] for row in factor_matrix], dtype=float)
            y = np.array([float(v) for v in targets], dtype=float)

            model = Ridge(alpha=max(self.config.l2_alpha, 1e-8), fit_intercept=True)
            model.fit(X, y)
            coef = model.coef_ if hasattr(model, "coef_") else []
            w = {n: max(float(c), 0.0) for n, c in zip(names, coef)}
            if sum(w.values()) <= 0:
                return {n: 1.0 for n in names}
            return w
        except Exception as exc:
            log.warn("ridge fit failed, fallback to equal", error=exc)
            return {n: 1.0 for n in names}

    def _fit_lasso(self, factor_matrix: List[Dict[str, float]], targets: List[float], names: List[str]) -> Dict[str, float]:
        if not factor_matrix or not targets or len(factor_matrix) != len(targets):
            return {n: 1.0 for n in names}

        try:
            import numpy as np
            from sklearn.linear_model import Lasso

            X = np.array([[float(row.get(n, 0.0)) for n in names] for row in factor_matrix], dtype=float)
            y = np.array([float(v) for v in targets], dtype=float)

            alpha = max(self.config.l2_alpha, 1e-4)
            model = Lasso(alpha=alpha, fit_intercept=True, max_iter=10000)
            model.fit(X, y)
            coef = model.coef_ if hasattr(model, "coef_") else []
            w = {n: max(float(c), 0.0) for n, c in zip(names, coef)}
            if sum(w.values()) <= 0:
                return {n: 1.0 for n in names}
            return w
        except Exception as exc:
            log.warn("lasso fit failed, fallback to equal", error=exc)
            return {n: 1.0 for n in names}


if __name__ == "__main__":
    # tiny smoke run
    matrix = [
        {"momentum_1m": 0.2, "rsi_14d": 40, "pe_ratio": -12},
        {"momentum_1m": -0.1, "rsi_14d": 70, "pe_ratio": -25},
        {"momentum_1m": 0.3, "rsi_14d": 35, "pe_ratio": -10},
    ]
    y = [0.04, -0.02, 0.06]
    ic_stats = {
        "momentum_1m": {"ic_mean": 0.05, "ic_ir": 0.8},
        "rsi_14d": {"ic_mean": 0.01, "ic_ir": 0.2},
        "pe_ratio": {"ic_mean": 0.03, "ic_ir": 0.6},
    }

    c = FactorCombiner(CombineConfig(method="ic_weighted", max_weight=0.30))
    w = c.fit(matrix, y, ic_stats=ic_stats)
    log.info("combiner weights", **{k: round(v, 4) for k, v in w.items()})
