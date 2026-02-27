"""Kelly-based dynamic position sizing (Phase 11)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from common.env_loader import load_env
from common.logger import get_logger

load_env()
log = get_logger("risk_sizer")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def kelly_fraction(win_rate: float, payoff_ratio: float) -> float:
    """Full Kelly fraction: f* = (b p - q) / b."""
    p = max(0.0, min(1.0, _safe_float(win_rate, 0.0)))
    b = _safe_float(payoff_ratio, 0.0)
    q = 1.0 - p
    if b <= 0:
        return 0.0
    f = (b * p - q) / b
    return max(0.0, f)


def half_kelly_fraction(win_rate: float, payoff_ratio: float) -> float:
    return max(0.0, min(1.0, kelly_fraction(win_rate, payoff_ratio) * 0.5))


@dataclass
class KellySizerConfig:
    max_single_position: float = 0.05
    max_total_exposure: float = 0.80
    atr_target: float = 0.02
    min_position_value: float = 0.0


class KellyPositionSizer:
    def __init__(self, config: Optional[KellySizerConfig] = None):
        self.config = config or KellySizerConfig()

    def size_position(
        self,
        account_equity: float,
        price: float,
        win_rate: float,
        payoff_ratio: float,
        current_total_exposure: float,
        atr_pct: Optional[float] = None,
        conviction: float = 1.0,
    ) -> dict:
        equity = max(_safe_float(account_equity), 0.0)
        px = max(_safe_float(price), 0.0)
        if equity <= 0 or px <= 0:
            return {
                "kelly_fraction": 0.0,
                "target_fraction": 0.0,
                "capped_fraction": 0.0,
                "target_value": 0.0,
                "quantity": 0.0,
                "reason": "invalid_input",
            }

        full_kelly = kelly_fraction(win_rate, payoff_ratio)
        base_fraction = half_kelly_fraction(win_rate, payoff_ratio)

        # optional conviction scaling (0~1+)
        conv = max(0.0, _safe_float(conviction, 1.0))
        target_fraction = base_fraction * conv

        # volatility scaling by ATR pct
        atr = _safe_float(atr_pct, 0.0)
        vol_scale = 1.0
        if atr > 0:
            target = max(self.config.atr_target, 1e-6)
            vol_scale = min(1.0, target / atr)
            target_fraction *= vol_scale

        # hard caps
        remaining = max(0.0, self.config.max_total_exposure - max(_safe_float(current_total_exposure), 0.0))
        capped_fraction = min(target_fraction, self.config.max_single_position, remaining)
        capped_fraction = max(0.0, capped_fraction)

        target_value = equity * capped_fraction
        if target_value < self.config.min_position_value:
            target_value = 0.0
            capped_fraction = 0.0

        qty = target_value / px if px > 0 else 0.0

        return {
            "full_kelly_fraction": round(full_kelly, 6),
            "kelly_fraction": round(base_fraction, 6),
            "target_fraction": round(target_fraction, 6),
            "volatility_scale": round(vol_scale, 6),
            "capped_fraction": round(capped_fraction, 6),
            "remaining_exposure_capacity": round(remaining, 6),
            "target_value": round(target_value, 6),
            "quantity": round(qty, 6),
            "max_single_position": self.config.max_single_position,
            "max_total_exposure": self.config.max_total_exposure,
        }

    def size_batch(
        self,
        account_equity: float,
        current_total_exposure: float,
        candidates: List[dict],
    ) -> List[dict]:
        """Greedy sizing for multiple candidates.

        Candidate fields:
        {symbol, price, win_rate, payoff_ratio, atr_pct?, conviction?}
        """
        out = []
        used = max(_safe_float(current_total_exposure), 0.0)

        # highest expected edge first
        ranked = sorted(
            candidates,
            key=lambda c: half_kelly_fraction(c.get("win_rate", 0.0), c.get("payoff_ratio", 0.0))
            * max(_safe_float(c.get("conviction", 1.0), 1.0), 0.0),
            reverse=True,
        )

        for c in ranked:
            res = self.size_position(
                account_equity=account_equity,
                price=c.get("price"),
                win_rate=c.get("win_rate"),
                payoff_ratio=c.get("payoff_ratio"),
                current_total_exposure=used,
                atr_pct=c.get("atr_pct"),
                conviction=c.get("conviction", 1.0),
            )
            res["symbol"] = c.get("symbol")
            out.append(res)
            used += _safe_float(res.get("capped_fraction"), 0.0)
            if used >= self.config.max_total_exposure:
                break

        return out


if __name__ == "__main__":
    sizer = KellyPositionSizer(KellySizerConfig(max_single_position=0.05, max_total_exposure=0.80))
    sample = sizer.size_position(
        account_equity=100000,
        price=250,
        win_rate=0.58,
        payoff_ratio=1.4,
        current_total_exposure=0.42,
        atr_pct=0.028,
        conviction=1.0,
    )
    log.info("kelly_size", **sample)
