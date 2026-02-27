"""Portfolio rebalancer (Phase 17)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if len(text) >= 10:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    return date.today()


@dataclass
class RebalanceConfig:
    drift_threshold: float = 0.05
    min_trade_notional: float = 100.0
    fee_bps: float = 5.0
    tax_bps_on_sell: float = 10.0


class PortfolioRebalancer:
    def __init__(self, config: Optional[RebalanceConfig] = None):
        self.config = config or RebalanceConfig()

    def should_rebalance(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        as_of: Optional[str] = None,
        last_rebalance_date: Optional[str] = None,
    ) -> dict:
        cur = {str(k).upper(): _safe_float(v, 0.0) for k, v in (current_weights or {}).items()}
        tgt = {str(k).upper(): _safe_float(v, 0.0) for k, v in (target_weights or {}).items()}

        assets = sorted(set(cur.keys()) | set(tgt.keys()))
        max_drift = 0.0
        drift_by_asset = {}
        for a in assets:
            drift = _safe_float(cur.get(a), 0.0) - _safe_float(tgt.get(a), 0.0)
            drift_by_asset[a] = round(drift, 8)
            max_drift = max(max_drift, abs(drift))

        today = _to_date(as_of)
        monthly_force = False
        if last_rebalance_date:
            last = _to_date(last_rebalance_date)
            monthly_force = (today.year, today.month) != (last.year, last.month)
        else:
            monthly_force = True

        return {
            "trigger": bool(max_drift >= self.config.drift_threshold or monthly_force),
            "max_abs_drift": round(max_drift, 8),
            "monthly_force": monthly_force,
            "drift_by_asset": drift_by_asset,
            "as_of": today.isoformat(),
        }

    def build_rebalance_orders(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        portfolio_value: float,
        prices: Optional[dict[str, float]] = None,
        as_of: Optional[str] = None,
        last_rebalance_date: Optional[str] = None,
    ) -> dict:
        check = self.should_rebalance(
            current_weights=current_weights,
            target_weights=target_weights,
            as_of=as_of,
            last_rebalance_date=last_rebalance_date,
        )
        if not check["trigger"]:
            return {
                "trigger": False,
                "reason": "within drift threshold",
                "orders": [],
                "summary": {
                    "total_buy_notional": 0.0,
                    "total_sell_notional": 0.0,
                    "estimated_cost": 0.0,
                },
                **check,
            }

        pv = max(_safe_float(portfolio_value, 0.0), 0.0)
        px = {str(k).upper(): max(_safe_float(v, 0.0), 0.0) for k, v in (prices or {}).items()}

        assets = sorted(set(current_weights.keys()) | set(target_weights.keys()))
        orders: list[dict] = []

        total_buy = 0.0
        total_sell = 0.0
        total_cost = 0.0

        for asset in assets:
            cur_w = _safe_float(current_weights.get(asset), 0.0)
            tgt_w = _safe_float(target_weights.get(asset), 0.0)
            diff_w = tgt_w - cur_w
            trade_notional = diff_w * pv

            if abs(trade_notional) < self.config.min_trade_notional:
                continue

            side = "BUY" if trade_notional > 0 else "SELL"
            notion = abs(trade_notional)
            price = px.get(asset.upper(), 1.0)
            qty = notion / price if price > 0 else 0.0

            fee = notion * (self.config.fee_bps / 10000.0)
            tax = notion * (self.config.tax_bps_on_sell / 10000.0) if side == "SELL" else 0.0
            cost = fee + tax

            orders.append(
                {
                    "asset": asset.upper(),
                    "side": side,
                    "target_weight": round(tgt_w, 8),
                    "current_weight": round(cur_w, 8),
                    "trade_weight": round(diff_w, 8),
                    "trade_notional": round(notion, 4),
                    "price": round(price, 8),
                    "qty": round(qty, 8),
                    "estimated_cost": round(cost, 4),
                }
            )

            total_cost += cost
            if side == "BUY":
                total_buy += notion
            else:
                total_sell += notion

        return {
            "trigger": True,
            "orders": orders,
            "summary": {
                "total_buy_notional": round(total_buy, 4),
                "total_sell_notional": round(total_sell, 4),
                "estimated_cost": round(total_cost, 4),
            },
            **check,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Portfolio rebalancer")
    parser.add_argument("--input-file", required=True, help="json with current_weights/target_weights/portfolio_value/prices")
    args = parser.parse_args()

    with open(args.input_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    out = PortfolioRebalancer().build_rebalance_orders(
        current_weights=payload.get("current_weights") or {},
        target_weights=payload.get("target_weights") or {},
        portfolio_value=payload.get("portfolio_value") or 0.0,
        prices=payload.get("prices") or {},
        as_of=payload.get("as_of"),
        last_rebalance_date=payload.get("last_rebalance_date"),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
