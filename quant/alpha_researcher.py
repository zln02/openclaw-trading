"""Alpha Researcher — 룰 기반 파라미터 그리드서치 (Phase Level 5).

알고리즘:
1. 파라미터 공간 정의 (config)
2. 각 파라미터 조합으로 KR daily_ohlcv walk-forward IC 계산
   - 6개월 훈련 / 1개월 검증 슬라이딩
3. IC/IR 비교: candidate > baseline +10% → winner
4. winner → brain/alpha/best_params.json 저장
5. 각 에이전트가 시작 시 best_params.json 로드

실행:
    python -m quant.alpha_researcher [--dry-run] [--market kr]
    scripts/run_alpha_researcher.sh
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common.config import BRAIN_PATH, ALPHA_PARAM_SPACE
from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase
from common.telegram import Priority, send_telegram

load_env()
log = get_logger("alpha_researcher")

ALPHA_DIR = BRAIN_PATH / "alpha"
BEST_PARAMS_PATH = ALPHA_DIR / "best_params.json"

# ── 기본 파라미터 공간 (config.ALPHA_PARAM_SPACE로 override 가능) ──────────────
_DEFAULT_PARAM_SPACE: Dict[str, List[Any]] = {
    "rsi_window":         [7, 14, 21],
    "momentum_lookback":  [5, 10, 20],
    "bb_window":          [15, 20, 30],
    "atr_multiplier":     [1.5, 2.0, 2.5],
}

# Walk-forward 슬라이딩 설정
_TRAIN_MONTHS = 6
_VALID_MONTHS = 1
_MIN_TRAIN_ROWS = 60   # 최소 훈련 캔들 수
_MIN_VALID_ROWS = 5    # 최소 검증 캔들 수


# ── Pure-math helpers ──────────────────────────────────────────────────────────

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _rank(values: List[float]) -> List[float]:
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    for rank, (idx, _) in enumerate(indexed, 1):
        ranks[idx] = float(rank)
    return ranks


def _spearman_ic(signals: List[float], returns: List[float]) -> float:
    pairs = [(s, r) for s, r in zip(signals, returns) if s is not None and r is not None]
    if len(pairs) < 5:
        return 0.0
    sx, sy = zip(*pairs)
    rx = _rank(list(sx))
    ry = _rank(list(sy))
    n = len(rx)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / n
    sx_ = (sum((a - mx) ** 2 for a in rx) / n) ** 0.5
    sy_ = (sum((b - my) ** 2 for b in ry) / n) ** 0.5
    if sx_ == 0 or sy_ == 0:
        return 0.0
    return round(cov / (sx_ * sy_), 6)


def _compute_ir(ic_series: List[float]) -> float:
    if len(ic_series) < 3:
        return 0.0
    n = len(ic_series)
    mean = sum(ic_series) / n
    std = (sum((x - mean) ** 2 for x in ic_series) / n) ** 0.5
    return round(mean / std, 4) if std != 0 else 0.0


# ── Technical indicator helpers ────────────────────────────────────────────────

def _calc_rsi(closes: List[float], window: int) -> float:
    if len(closes) < window + 1:
        return 50.0
    gains = [max(closes[i] - closes[i-1], 0) for i in range(-window, 0)]
    losses = [max(closes[i-1] - closes[i], 0) for i in range(-window, 0)]
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _calc_momentum(closes: List[float], lookback: int) -> float:
    if len(closes) <= lookback:
        return 0.0
    prev = closes[-1 - lookback]
    cur = closes[-1]
    if prev <= 0:
        return 0.0
    return (cur / prev - 1) * 100.0


def _calc_bb_position(closes: List[float], window: int) -> float:
    if len(closes) < window:
        return 50.0
    w = [float(x) for x in closes[-window:]]
    m = sum(w) / len(w)
    s = (sum((x - m) ** 2 for x in w) / len(w)) ** 0.5
    upper = m + 2 * s
    lower = m - 2 * s
    width = upper - lower
    if width <= 0:
        return 50.0
    pos = (closes[-1] - lower) / width * 100.0
    return float(max(0, min(100, pos)))


def _calc_composite_signal(
    closes: List[float],
    params: Dict[str, Any],
) -> float:
    """파라미터 기반 단일 복합 신호 [-100, 100] (높을수록 BUY)."""
    rsi_w = int(params.get("rsi_window", 14))
    mom_lb = int(params.get("momentum_lookback", 10))
    bb_w = int(params.get("bb_window", 20))

    rsi = _calc_rsi(closes, rsi_w)
    mom = _calc_momentum(closes, mom_lb)
    bb_pos = _calc_bb_position(closes, bb_w)

    # RSI 신호: 낮을수록 매수 (+)
    rsi_sig = (50.0 - rsi) / 50.0 * 100.0         # RSI 50 → 0, RSI 30 → +40

    # 모멘텀: 양수면 매수
    mom_sig = max(-100.0, min(100.0, mom * 3))

    # BB: 낮은 위치(하단 근처)가 매수 (+)
    bb_sig = (50.0 - bb_pos) / 50.0 * 100.0       # BB 25% → +50

    return round((rsi_sig * 0.4 + mom_sig * 0.3 + bb_sig * 0.3), 4)


# ── Walk-forward IC 계산 ───────────────────────────────────────────────────────

def _walk_forward_ic(
    rows: List[Dict],
    params: Dict[str, Any],
    train_months: int = _TRAIN_MONTHS,
    valid_months: int = _VALID_MONTHS,
    forward_days: int = 3,
) -> Tuple[float, float, int]:
    """Walk-forward IC/IR 계산.

    Returns:
        (ic_mean, ir, n_windows)
    """
    if len(rows) < _MIN_TRAIN_ROWS + _MIN_VALID_ROWS:
        return 0.0, 0.0, 0

    closes = [_safe_float(r.get("close_price") or r.get("close"), 0) for r in rows]
    n = len(closes)

    # approx trading days per month
    train_days = train_months * 21
    valid_days = valid_months * 21

    ic_series: List[float] = []
    start = train_days

    while start + valid_days + forward_days <= n:
        valid_end = start + valid_days
        signals, returns = [], []

        for t in range(start, min(valid_end, n - forward_days)):
            sig = _calc_composite_signal(closes[:t + 1], params)
            fwd_ret = (closes[t + forward_days] - closes[t]) / closes[t] * 100
            signals.append(sig)
            returns.append(fwd_ret)

        if len(signals) >= 5:
            ic = _spearman_ic(signals, returns)
            ic_series.append(ic)

        start += valid_days

    if not ic_series:
        return 0.0, 0.0, 0

    ic_mean = round(sum(ic_series) / len(ic_series), 6)
    ir = _compute_ir(ic_series)
    return ic_mean, ir, len(ic_series)


# ── AlphaResearcher ────────────────────────────────────────────────────────────

class AlphaResearcher:
    def __init__(self, supabase_client=None, market: str = "kr"):
        self.supabase = supabase_client or get_supabase()
        self.market = market.lower()
        self._param_space = ALPHA_PARAM_SPACE if ALPHA_PARAM_SPACE else _DEFAULT_PARAM_SPACE

    # ── Data loading ──────────────────────────────────────────────────────

    def _load_ohlcv_series(self, limit_per_stock: int = 500) -> List[Tuple[str, List[Dict]]]:
        """종목별 OHLCV 시계열 로드."""
        if not self.supabase:
            log.warning("supabase 미연결 — 빈 데이터")
            return []

        try:
            stocks = (
                self.supabase.table("top50_stocks")
                .select("stock_code")
                .limit(30)
                .execute()
                .data or []
            )
        except Exception as exc:
            log.warning("top50 로드 실패", error=exc)
            return []

        result = []
        for s in stocks:
            code = s.get("stock_code") or s.get("symbol", "")
            if not code:
                continue
            try:
                rows = (
                    self.supabase.table("daily_ohlcv")
                    .select("date,close_price,volume")
                    .eq("stock_code", code)
                    .order("date", desc=False)
                    .limit(limit_per_stock)
                    .execute()
                    .data or []
                )
                if len(rows) >= _MIN_TRAIN_ROWS + _MIN_VALID_ROWS + 10:
                    result.append((code, rows))
            except Exception as exc:
                log.warning("ohlcv 로드 실패", code=code, error=exc)
        return result

    # ── Grid search ──────────────────────────────────────────────────────

    def _grid_search(
        self, stock_series: List[Tuple[str, List[Dict]]], dry_run: bool = False
    ) -> List[Dict[str, Any]]:
        """파라미터 공간 전체 grid search."""
        keys = list(self._param_space.keys())
        values = [self._param_space[k] for k in keys]
        combos = list(product(*values))

        log.info("grid search 시작", n_combos=len(combos), n_stocks=len(stock_series))
        results = []

        for combo in combos:
            params = dict(zip(keys, combo))

            # 모든 종목에 대해 walk-forward IC 평균
            all_ic, all_ir, total_windows = [], [], 0
            for code, rows in stock_series:
                ic, ir, nw = _walk_forward_ic(rows, params)
                if nw > 0:
                    all_ic.append(ic)
                    all_ir.append(ir)
                    total_windows += nw

            if not all_ic:
                continue

            avg_ic = round(sum(all_ic) / len(all_ic), 6)
            avg_ir = round(sum(all_ir) / len(all_ir), 4)
            results.append({
                "params": params,
                "ic": avg_ic,
                "ir": avg_ir,
                "n_stocks": len(all_ic),
                "n_windows": total_windows,
            })

            if dry_run:
                log.info("dry-run combo", params=params, ic=avg_ic, ir=avg_ir)

        results.sort(key=lambda x: x["ir"], reverse=True)
        return results

    # ── Baseline ─────────────────────────────────────────────────────────

    def _load_baseline(self) -> Optional[Dict]:
        if BEST_PARAMS_PATH.exists():
            try:
                return json.loads(BEST_PARAMS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    # ── Main ─────────────────────────────────────────────────────────────

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        log.info("alpha research 시작", market=self.market, dry_run=dry_run)
        ALPHA_DIR.mkdir(parents=True, exist_ok=True)

        stock_series = self._load_ohlcv_series()
        if not stock_series:
            log.warning("데이터 없음 — 종료")
            return {"status": "NO_DATA"}

        results = self._grid_search(stock_series, dry_run=dry_run)
        if not results:
            log.warning("grid search 결과 없음")
            return {"status": "NO_RESULTS"}

        winner = results[0]
        baseline = self._load_baseline()
        baseline_ir = float((baseline or {}).get("ir", 0.0))

        improved = winner["ir"] > baseline_ir * 1.10  # +10% 이상 개선
        improvement_pct = round((winner["ir"] - baseline_ir) / max(baseline_ir, 0.01) * 100, 1)

        report: Dict[str, Any] = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "market": self.market,
            "params": winner["params"],
            "ic": winner["ic"],
            "ir": winner["ir"],
            "n_stocks": winner["n_stocks"],
            "n_windows": winner["n_windows"],
            "baseline_ir": baseline_ir,
            "improved": improved,
            "improvement_pct": improvement_pct,
            "top5_results": results[:5],
        }

        if not dry_run and improved:
            BEST_PARAMS_PATH.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log.info(
                "best_params 업데이트",
                params=winner["params"],
                ir=winner["ir"],
                improvement_pct=improvement_pct,
            )
        elif not dry_run:
            log.info(
                "기존 파라미터 유지",
                current_ir=winner["ir"],
                baseline_ir=baseline_ir,
            )

        # 텔레그램 알림
        try:
            status_emoji = "🔄" if improved else "✅"
            lines = [
                f"{status_emoji} <b>알파 리서치 완료</b> ({self.market.upper()})",
                f"분석: {winner['n_stocks']}종목 / {winner['n_windows']}윈도우",
                f"Winner IC={winner['ic']:+.4f} IR={winner['ir']:+.4f}",
                f"Baseline IR={baseline_ir:+.4f} → 개선: {improvement_pct:+.1f}%",
                "",
                f"최적 파라미터:",
            ]
            for k, v in winner["params"].items():
                lines.append(f"  {k}: {v}")
            if improved:
                lines.append("\n✅ best_params.json 업데이트됨")
            send_telegram("\n".join(lines), priority=Priority.INFO)
        except Exception as exc:
            log.warning("telegram 알림 실패", error=exc)

        return report


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli() -> int:
    p = argparse.ArgumentParser(description="Alpha researcher — 룰 기반 파라미터 그리드서치")
    p.add_argument("--market", default="kr", help="시장 (kr|us|btc)")
    p.add_argument("--dry-run", action="store_true", help="저장/알림 없이 결과만 출력")
    args = p.parse_args()

    researcher = AlphaResearcher(market=args.market)
    result = researcher.run(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
