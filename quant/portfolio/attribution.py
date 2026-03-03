"""Performance attribution utilities (Phase 17 → Level 5 확장).

신규 (Level 5):
- WeeklyAttributionRunner: Supabase trade_executions + factor_snapshot 기반
  팩터별 PnL 기여도 계산 → 주간 텔레그램 보고서 → 저품질 팩터 다운웨이팅
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


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


class WeeklyAttributionRunner:
    """Supabase 기반 주간 팩터 PnL 귀속 분석 (Level 5 핵심).

    trade_executions의 factor_snapshot + pnl_pct를 읽어
    팩터별 수익 기여를 계산하고 weights.json을 자동 업데이트한다.
    """

    def __init__(self, supabase_client=None):
        try:
            from common.supabase_client import get_supabase
            self.supabase = supabase_client or get_supabase()
        except Exception:
            self.supabase = None

        try:
            from common.config import BRAIN_PATH
            self._weights_path = BRAIN_PATH / "signal-ic" / "weights.json"
        except Exception:
            self._weights_path = Path("/home/wlsdud5035/.openclaw/workspace/brain/signal-ic/weights.json")

    # ── Data loading ──────────────────────────────────────────────────────

    def _load_closed_trades(self, lookback_days: int = 7) -> List[Dict[str, Any]]:
        """지난 N일간 체결된 trades (factor_snapshot 있는 것만)."""
        if not self.supabase:
            return []
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=lookback_days)
        ).date().isoformat()
        try:
            rows = (
                self.supabase.table("trade_executions")
                .select("stock_code,factor_snapshot,price,quantity,entry_price")
                .eq("result", "CLOSED")
                .eq("trade_type", "SELL")
                .gte("created_at", cutoff)
                .execute()
                .data or []
            )
        except Exception as exc:
            try:
                from common.logger import get_logger
                get_logger("attribution").warning("trade 로드 실패", error=exc)
            except Exception:
                pass
            return []

        result = []
        for r in rows:
            snap_raw = r.get("factor_snapshot")
            if not snap_raw:
                continue
            try:
                snap = json.loads(snap_raw) if isinstance(snap_raw, str) else snap_raw
            except Exception:
                continue
            if not isinstance(snap, dict):
                continue
            # PnL 계산: price/entry_price에서 직접 계산
            entry = _safe_float(r.get("entry_price"), 0.0)
            sell = _safe_float(r.get("price"), 0.0)
            if entry > 0 and sell > 0:
                pnl = (sell - entry) / entry * 100.0
            else:
                continue
            result.append({"pnl_pct": pnl, "factors": snap})
        return result

    # ── Attribution calculation ───────────────────────────────────────────

    def _calc_factor_attribution(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        """팩터별 PnL 기여도 집계.

        Factor Contribution per trade = position_return × normalized_factor_weight
        Returns: {factor_name: {total_contrib, n_trades, avg_contrib, avg_pnl}}
        """
        factor_stats: Dict[str, List[float]] = {}

        for trade in trades:
            pnl = trade["pnl_pct"]
            factors = trade["factors"]
            if not factors:
                continue

            # 팩터 절대값 합으로 정규화 → 각 팩터의 가중치 비율
            total_abs = sum(abs(v) for v in factors.values())
            if total_abs <= 0:
                continue

            for fname, fval in factors.items():
                weight = abs(_safe_float(fval, 0.0)) / total_abs
                contrib = pnl * weight
                if fname not in factor_stats:
                    factor_stats[fname] = []
                factor_stats[fname].append(contrib)

        result: Dict[str, Dict[str, float]] = {}
        for fname, contribs in factor_stats.items():
            n = len(contribs)
            total = sum(contribs)
            result[fname] = {
                "total_contrib": round(total, 4),
                "n_trades": n,
                "avg_contrib": round(total / n, 4) if n > 0 else 0.0,
            }

        return result

    # ── Weights update ────────────────────────────────────────────────────

    def _downweight_low_contributors(
        self,
        factor_attrs: Dict[str, Dict[str, float]],
        threshold_avg: float = -0.5,
        decay: float = 0.5,
    ) -> bool:
        """avg_contrib < threshold인 팩터를 weights.json에서 다운웨이팅."""
        if not self._weights_path.exists():
            return False
        try:
            payload = json.loads(self._weights_path.read_text(encoding="utf-8"))
        except Exception:
            return False

        weights: Dict[str, float] = payload.get("weights", {})
        if not weights:
            return False

        changed = False
        for fname, stats in factor_attrs.items():
            if fname in weights and stats["avg_contrib"] < threshold_avg:
                old_w = weights[fname]
                weights[fname] = round(max(0.0, old_w * decay), 6)
                changed = True

        if not changed:
            return False

        # 재정규화
        total = sum(v for v in weights.values() if v > 0)
        if total > 0:
            payload["weights"] = {k: round(v / total, 6) for k, v in weights.items() if v > 0}

        payload["attribution_updated"] = datetime.now(timezone.utc).isoformat()
        self._weights_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    # ── Telegram report ───────────────────────────────────────────────────

    def _send_report(
        self,
        factor_attrs: Dict[str, Dict[str, float]],
        n_trades: int,
        total_pnl_avg: float,
        weights_updated: bool,
    ) -> None:
        try:
            from common.telegram import Priority, send_telegram
        except Exception:
            return

        sorted_factors = sorted(
            factor_attrs.items(), key=lambda x: x[1]["total_contrib"], reverse=True
        )

        lines = [
            "📊 <b>주간 팩터 귀속 분석 (Attribution)</b>",
            f"대상 trades: {n_trades}건 | 평균 PnL: {total_pnl_avg:+.2f}%",
            "",
            "<b>팩터별 수익 기여도 (상위 5):</b>",
        ]
        for fname, stats in sorted_factors[:5]:
            icon = "✅" if stats["avg_contrib"] >= 0 else "⚠️"
            lines.append(
                f"  {icon} {fname}: 합계={stats['total_contrib']:+.2f}% "
                f"평균={stats['avg_contrib']:+.2f}% ({stats['n_trades']}건)"
            )

        if weights_updated:
            lines.append("\n🔄 저기여 팩터 다운웨이팅 완료 → weights.json 업데이트")

        try:
            send_telegram("\n".join(lines), priority=Priority.INFO)
        except Exception:
            pass

    # ── Main ─────────────────────────────────────────────────────────────

    def run(self, lookback_days: int = 7, dry_run: bool = False) -> Dict[str, Any]:
        try:
            from common.logger import get_logger
            log = get_logger("attribution_runner")
        except Exception:
            import logging
            log = logging.getLogger("attribution_runner")

        log.info("attribution 분석 시작", lookback_days=lookback_days)

        trades = self._load_closed_trades(lookback_days=lookback_days)
        if not trades:
            log.warning("factor_snapshot 포함 trades 없음 — 데이터 축적 필요")
            return {"status": "NO_DATA", "n_trades": 0}

        factor_attrs = self._calc_factor_attribution(trades)
        n_trades = len(trades)
        total_pnl_avg = round(
            sum(t["pnl_pct"] for t in trades) / n_trades, 4
        ) if n_trades > 0 else 0.0

        weights_updated = False
        if not dry_run:
            weights_updated = self._downweight_low_contributors(factor_attrs)

        self._send_report(factor_attrs, n_trades, total_pnl_avg, weights_updated)

        return {
            "status": "OK",
            "n_trades": n_trades,
            "total_pnl_avg": total_pnl_avg,
            "factor_attribution": factor_attrs,
            "weights_updated": weights_updated,
            "timestamp": _utc_now_iso(),
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Performance attribution")
    parser.add_argument("--input-file", default=None, help="json with portfolio/benchmark data")
    parser.add_argument("--weekly", action="store_true", help="주간 attribution 실행 (Supabase)")
    parser.add_argument("--lookback", type=int, default=7, help="lookback days (--weekly 전용)")
    parser.add_argument("--dry-run", action="store_true", help="저장/알림 없이 출력만")
    args = parser.parse_args()

    if args.weekly:
        runner = WeeklyAttributionRunner()
        out = runner.run(lookback_days=args.lookback, dry_run=args.dry_run)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if not args.input_file:
        parser.error("--input-file 또는 --weekly 필요")

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
