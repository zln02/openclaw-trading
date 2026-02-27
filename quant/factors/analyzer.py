"""Factor performance analyzer (Phase 10).

Metrics:
- IC (Information Coefficient): factor vs next-period return
- IC mean / IC IR
- Monotonicity test by quantiles
- Quantile spread (Q5 - Q1)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from common.env_loader import load_env
from common.logger import get_logger
from quant.factors.registry import FactorContext, available_factors, calc

load_env()
log = get_logger("factor_analyzer")


def _to_iso_day(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text[:10] if len(text) >= 10 else text


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


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


def _corr(x: Sequence[float], y: Sequence[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    xs = [float(v) for v in x[:n]]
    ys = [float(v) for v in y[:n]]
    mx = _mean(xs)
    my = _mean(ys)
    vx = sum((v - mx) ** 2 for v in xs)
    vy = sum((v - my) ** 2 for v in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    return float(cov / math.sqrt(vx * vy))


def _quantile_buckets(pairs: List[Tuple[float, float]], q: int = 5) -> List[List[Tuple[float, float]]]:
    if not pairs or q <= 1:
        return [pairs]
    arr = sorted(pairs, key=lambda x: x[0])
    n = len(arr)
    buckets: List[List[Tuple[float, float]]] = []
    for i in range(q):
        lo = int(i * n / q)
        hi = int((i + 1) * n / q)
        if hi <= lo:
            continue
        buckets.append(arr[lo:hi])
    return buckets


def _monotonicity_ratio(quantile_means: List[float]) -> float:
    if len(quantile_means) < 2:
        return 0.0
    good = 0
    total = len(quantile_means) - 1
    for i in range(total):
        if quantile_means[i + 1] >= quantile_means[i]:
            good += 1
    return good / total


def _month_end_dates(start_iso: str, end_iso: str) -> List[str]:
    s = datetime.strptime(_to_iso_day(start_iso), "%Y-%m-%d").date()
    e = datetime.strptime(_to_iso_day(end_iso), "%Y-%m-%d").date()
    if s > e:
        return []

    out: List[str] = []
    cur = date(s.year, s.month, 1)
    while cur <= e:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        month_end = min(nxt - timedelta(days=1), e)
        if month_end >= s:
            out.append(month_end.isoformat())
        cur = nxt
    return out


@dataclass
class FactorAnalysisResult:
    factor_name: str
    ic_mean: float
    ic_ir: float
    quantile_spread: float
    monotonicity: float
    is_valid: bool
    observation_count: int
    period_count: int

    def to_dict(self) -> dict:
        return {
            "factor_name": self.factor_name,
            "ic_mean": round(self.ic_mean, 6),
            "ic_ir": round(self.ic_ir, 6),
            "quantile_spread": round(self.quantile_spread, 6),
            "monotonicity": round(self.monotonicity, 6),
            "is_valid": bool(self.is_valid),
            "observation_count": int(self.observation_count),
            "period_count": int(self.period_count),
        }


class FactorAnalyzer:
    def __init__(self, context: Optional[FactorContext] = None):
        self.context = context or FactorContext()

    def _forward_return(
        self,
        symbol: str,
        as_of_iso: str,
        market: str,
        horizon_days: int,
    ) -> Optional[float]:
        rows = self.context.get_ohlcv(symbol, as_of_iso, market=market, lookback=5000)
        if not rows:
            return None

        # `get_ohlcv(..., as_of_iso)` is <= as_of only, so for forward return we query
        # directly from context cache by asking a far-future as_of and then filtering.
        all_rows = self.context.get_ohlcv(symbol, "2999-12-31", market=market, lookback=10000)
        if not all_rows:
            return None

        idx = None
        for i, r in enumerate(all_rows):
            if str(r.get("date") or "")[:10] <= as_of_iso:
                idx = i
            else:
                break
        if idx is None:
            return None

        j = idx + max(horizon_days, 1)
        if j >= len(all_rows):
            return None

        p0 = _safe_float(all_rows[idx].get("close"), 0.0)
        p1 = _safe_float(all_rows[j].get("close"), 0.0)
        if p0 <= 0 or p1 <= 0:
            return None
        return (p1 / p0) - 1.0

    def analyze_factor(
        self,
        factor_name: str,
        symbols: Iterable[str],
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        market: str = "kr",
        horizon_days: int = 21,
        min_cross_section: int = 10,
    ) -> FactorAnalysisResult:
        start_iso = _to_iso_day(start_date)
        end_iso = _to_iso_day(end_date)
        eval_dates = _month_end_dates(start_iso, end_iso)

        ics: List[float] = []
        spreads: List[float] = []
        mono_scores: List[float] = []
        obs_count = 0

        symbol_list = [str(s).strip().upper() for s in symbols if str(s).strip()]

        for d in eval_dates:
            pairs: List[Tuple[float, float]] = []
            for sym in symbol_list:
                fv = calc(
                    factor_name,
                    as_of=d,
                    symbol=sym,
                    market=market,
                    context=self.context,
                )
                fr = self._forward_return(sym, d, market=market, horizon_days=horizon_days)
                if fr is None:
                    continue
                if math.isnan(fv) or math.isnan(fr):
                    continue
                pairs.append((float(fv), float(fr)))

            if len(pairs) < max(min_cross_section, 2):
                continue

            xs = [x for x, _ in pairs]
            ys = [y for _, y in pairs]
            ic = _corr(xs, ys)
            ics.append(ic)
            obs_count += len(pairs)

            buckets = _quantile_buckets(pairs, q=5)
            if len(buckets) >= 2:
                q_means = [_mean([r for _, r in b]) for b in buckets]
                spreads.append(q_means[-1] - q_means[0])
                mono_scores.append(_monotonicity_ratio(q_means))

        ic_mean = _mean(ics)
        ic_std = _std(ics)
        ic_ir = (ic_mean / ic_std) if ic_std > 0 else 0.0
        quantile_spread = _mean(spreads)
        monotonicity = _mean(mono_scores)

        is_valid = (ic_mean > 0.03) and (ic_ir > 0.5)

        return FactorAnalysisResult(
            factor_name=factor_name,
            ic_mean=ic_mean,
            ic_ir=ic_ir,
            quantile_spread=quantile_spread,
            monotonicity=monotonicity,
            is_valid=is_valid,
            observation_count=obs_count,
            period_count=len(ics),
        )

    def analyze_many(
        self,
        factor_names: Optional[Iterable[str]],
        symbols: Iterable[str],
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        market: str = "kr",
        horizon_days: int = 21,
        min_cross_section: int = 10,
    ) -> List[dict]:
        names = list(factor_names) if factor_names is not None else available_factors(universe=market)
        results: List[dict] = []
        for name in names:
            try:
                r = self.analyze_factor(
                    name,
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    market=market,
                    horizon_days=horizon_days,
                    min_cross_section=min_cross_section,
                )
                results.append(r.to_dict())
            except Exception as exc:
                log.warn("factor analysis failed", factor=name, error=exc)
        results.sort(key=lambda x: (x.get("is_valid", False), x.get("ic_ir", 0.0), x.get("ic_mean", 0.0)), reverse=True)
        return results


if __name__ == "__main__":
    from quant.backtest.universe import UniverseProvider

    up = UniverseProvider()
    end = datetime.now().date().isoformat()
    start = (datetime.now().date() - timedelta(days=365 * 2)).isoformat()
    syms = up.get_universe(end, market="kr", max_symbols=30)

    analyzer = FactorAnalyzer()
    out = analyzer.analyze_factor(
        "momentum_1m",
        symbols=syms,
        start_date=start,
        end_date=end,
        market="kr",
    )
    log.info("factor_analysis", **out.to_dict())
