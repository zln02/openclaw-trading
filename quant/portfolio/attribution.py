"""Performance attribution utilities (Phase 17)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


@dataclass
class AttributionRow:
    asset: str
    portfolio_weight: float
    benchmark_weight: float
    portfolio_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_effect: float

    def to_dict(self) -> dict:
        return asdict(self)


def brinson_attribution(
    portfolio_weights: Mapping[str, float],
    benchmark_weights: Mapping[str, float],
    portfolio_returns: Mapping[str, float],
    benchmark_returns: Mapping[str, float],
) -> dict:
    assets = sorted(
        set(str(k).upper() for k in portfolio_weights.keys())
        | set(str(k).upper() for k in benchmark_weights.keys())
        | set(str(k).upper() for k in portfolio_returns.keys())
        | set(str(k).upper() for k in benchmark_returns.keys())
    )

    rb_total = 0.0
    for a in assets:
        wb = _safe_float(benchmark_weights.get(a), 0.0)
        rb = _safe_float(benchmark_returns.get(a), 0.0)
        rb_total += wb * rb

    rows: list[dict] = []
    alloc_sum = 0.0
    sel_sum = 0.0
    inter_sum = 0.0

    for a in assets:
        wp = _safe_float(portfolio_weights.get(a), 0.0)
        wb = _safe_float(benchmark_weights.get(a), 0.0)
        rp = _safe_float(portfolio_returns.get(a), 0.0)
        rb = _safe_float(benchmark_returns.get(a), 0.0)

        alloc = (wp - wb) * (rb - rb_total)
        sel = wb * (rp - rb)
        inter = (wp - wb) * (rp - rb)
        total = alloc + sel + inter

        alloc_sum += alloc
        sel_sum += sel
        inter_sum += inter

        rows.append(
            AttributionRow(
                asset=a,
                portfolio_weight=round(wp, 8),
                benchmark_weight=round(wb, 8),
                portfolio_return=round(rp, 8),
                benchmark_return=round(rb, 8),
                allocation_effect=round(alloc, 10),
                selection_effect=round(sel, 10),
                interaction_effect=round(inter, 10),
                total_effect=round(total, 10),
            ).to_dict()
        )

    total_active = alloc_sum + sel_sum + inter_sum
    return {
        "rows": rows,
        "allocation_effect": round(alloc_sum, 10),
        "selection_effect": round(sel_sum, 10),
        "interaction_effect": round(inter_sum, 10),
        "active_return": round(total_active, 10),
        "timestamp": _utc_now_iso(),
    }


class PerformanceAttribution:
    def factor_contribution(
        self,
        factor_exposure: Mapping[str, float],
        factor_return: Mapping[str, float],
    ) -> dict:
        names = sorted(set(factor_exposure.keys()) | set(factor_return.keys()))
        rows = []
        total = 0.0

        for n in names:
            exp = _safe_float(factor_exposure.get(n), 0.0)
            ret = _safe_float(factor_return.get(n), 0.0)
            contrib = exp * ret
            total += contrib
            rows.append(
                {
                    "factor": str(n),
                    "exposure": round(exp, 8),
                    "factor_return": round(ret, 8),
                    "contribution": round(contrib, 10),
                }
            )

        rows.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        return {
            "rows": rows,
            "total_factor_contribution": round(total, 10),
        }

    def report(
        self,
        portfolio_weights: Mapping[str, float],
        benchmark_weights: Mapping[str, float],
        portfolio_returns: Mapping[str, float],
        benchmark_returns: Mapping[str, float],
        factor_exposure: Optional[Mapping[str, float]] = None,
        factor_return: Optional[Mapping[str, float]] = None,
        month: Optional[str] = None,
    ) -> dict:
        br = brinson_attribution(
            portfolio_weights=portfolio_weights,
            benchmark_weights=benchmark_weights,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
        )
        fac = self.factor_contribution(factor_exposure or {}, factor_return or {})

        return {
            "month": month or datetime.now().strftime("%Y-%m"),
            "brinson": br,
            "factor": fac,
            "summary": {
                "active_return": br.get("active_return", 0.0),
                "allocation_effect": br.get("allocation_effect", 0.0),
                "selection_effect": br.get("selection_effect", 0.0),
                "interaction_effect": br.get("interaction_effect", 0.0),
                "factor_total": fac.get("total_factor_contribution", 0.0),
            },
            "timestamp": _utc_now_iso(),
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Performance attribution")
    parser.add_argument("--input-file", required=True, help="json with portfolio/benchmark data")
    args = parser.parse_args()

    with open(args.input_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    out = PerformanceAttribution().report(
        portfolio_weights=payload.get("portfolio_weights") or {},
        benchmark_weights=payload.get("benchmark_weights") or {},
        portfolio_returns=payload.get("portfolio_returns") or {},
        benchmark_returns=payload.get("benchmark_returns") or {},
        factor_exposure=payload.get("factor_exposure") or {},
        factor_return=payload.get("factor_return") or {},
        month=payload.get("month"),
    )

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
