"""BTC funding carry strategy (Phase 14).

Core rule:
- funding > +0.05%: spot BUY + perpetual SHORT (delta-neutral)
- funding < -0.03%: spot SELL + perpetual LONG (delta-neutral)
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, Optional

from common.env_loader import load_env
from common.logger import get_logger
from common.market_data import get_btc_funding_rate

load_env()
log = get_logger("btc_funding_carry")


@dataclass
class FundingCarryDecision:
    symbol: str
    funding_rate_pct: float
    action: str
    spot_side: str
    futures_side: str
    hedge_ratio: float
    est_daily_carry_pct: float
    est_annual_carry_pct: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HedgeOrderPlan:
    symbol: str
    action: str
    spot_side: str
    futures_side: str
    spot_notional: float
    futures_notional: float

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def build_funding_carry_decision(
    funding_rate_pct: float,
    symbol: str = "BTCUSDT",
    positive_threshold_pct: float = 0.05,
    negative_threshold_pct: float = -0.03,
    funding_intervals_per_day: int = 3,
) -> dict:
    rate = _safe_float(funding_rate_pct, 0.0)
    pos_th = _safe_float(positive_threshold_pct, 0.05)
    neg_th = _safe_float(negative_threshold_pct, -0.03)
    intervals = max(int(funding_intervals_per_day), 1)

    if rate >= pos_th:
        action = "CARRY_SHORT_PERP"
        spot_side = "BUY"
        futures_side = "SELL"
        reason = f"funding {rate:.4f}% >= +{pos_th:.4f}%"
    elif rate <= neg_th:
        action = "CARRY_LONG_PERP"
        spot_side = "SELL"
        futures_side = "BUY"
        reason = f"funding {rate:.4f}% <= {neg_th:.4f}%"
    else:
        action = "NO_TRADE"
        spot_side = "HOLD"
        futures_side = "HOLD"
        reason = f"funding {rate:.4f}% inside neutral band"

    est_daily = abs(rate) * intervals
    est_annual = est_daily * 365.0

    decision = FundingCarryDecision(
        symbol=str(symbol or "BTCUSDT").upper(),
        funding_rate_pct=round(rate, 6),
        action=action,
        spot_side=spot_side,
        futures_side=futures_side,
        hedge_ratio=1.0,
        est_daily_carry_pct=round(est_daily, 6),
        est_annual_carry_pct=round(est_annual, 4),
        reason=reason,
    )
    return decision.to_dict()


class FundingCarryStrategy:
    def __init__(
        self,
        funding_fetcher: Optional[Callable[[], dict]] = None,
        positive_threshold_pct: float = 0.05,
        negative_threshold_pct: float = -0.03,
        funding_intervals_per_day: int = 3,
    ):
        self.funding_fetcher = funding_fetcher or get_btc_funding_rate
        self.positive_threshold_pct = positive_threshold_pct
        self.negative_threshold_pct = negative_threshold_pct
        self.funding_intervals_per_day = funding_intervals_per_day

    def current_rate_pct(self) -> float:
        try:
            row = self.funding_fetcher() or {}
            # common.market_data.get_btc_funding_rate() returns percent already.
            return _safe_float(row.get("rate"), 0.0)
        except Exception as exc:
            log.warn("funding fetch failed", error=exc)
            return 0.0

    def evaluate(self, symbol: str = "BTCUSDT", funding_rate_pct: Optional[float] = None) -> dict:
        rate = self.current_rate_pct() if funding_rate_pct is None else _safe_float(funding_rate_pct, 0.0)
        return build_funding_carry_decision(
            funding_rate_pct=rate,
            symbol=symbol,
            positive_threshold_pct=self.positive_threshold_pct,
            negative_threshold_pct=self.negative_threshold_pct,
            funding_intervals_per_day=self.funding_intervals_per_day,
        )

    def build_hedge_plan(self, notional: float, symbol: str = "BTCUSDT", funding_rate_pct: Optional[float] = None) -> dict:
        decision = self.evaluate(symbol=symbol, funding_rate_pct=funding_rate_pct)
        notional_value = max(_safe_float(notional, 0.0), 0.0)

        plan = HedgeOrderPlan(
            symbol=decision["symbol"],
            action=decision["action"],
            spot_side=decision["spot_side"],
            futures_side=decision["futures_side"],
            spot_notional=round(notional_value, 4),
            futures_notional=round(notional_value * _safe_float(decision.get("hedge_ratio"), 1.0), 4),
        )

        out = {"decision": decision, "hedge_plan": plan.to_dict()}
        return out


def _cli() -> int:
    parser = argparse.ArgumentParser(description="BTC funding carry strategy")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--funding-rate", type=float, default=None, help="override funding rate in percent")
    parser.add_argument("--notional", type=float, default=10000.0)
    parser.add_argument("--pos-threshold", type=float, default=0.05)
    parser.add_argument("--neg-threshold", type=float, default=-0.03)
    args = parser.parse_args()

    strategy = FundingCarryStrategy(
        positive_threshold_pct=args.pos_threshold,
        negative_threshold_pct=args.neg_threshold,
    )
    out = strategy.build_hedge_plan(
        notional=args.notional,
        symbol=args.symbol,
        funding_rate_pct=args.funding_rate,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
