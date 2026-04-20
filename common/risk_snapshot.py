"""리스크 스냅샷 빌더 — VaR·드로다운·포지션을 brain/risk/latest_snapshot.json에 저장."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from common.config import BRAIN_PATH
from common.equity_loader import load_all_positions
from common.utils import safe_float as _safe_float
from common.utils import utc_now as _utc_now
from quant.risk.var_model import VaRModel, fetch_return_matrix


def _equity_snapshot_path(market: str) -> Path:
    return BRAIN_PATH / "equity" / f"{market}.jsonl"


def _risk_snapshot_path() -> Path:
    return BRAIN_PATH / "risk" / "latest_snapshot.json"


def _proxy_symbol(symbol: str) -> str:
    sym = str(symbol or "").upper().strip()
    if not sym:
        return ""
    if sym == "BTC":
        return "BTC-USD"
    if sym.startswith("A") and sym[1:].isdigit():
        return f"{sym[1:]}.KS"
    if sym.isdigit():
        return f"{sym}.KS"
    return sym


def _load_latest_equity_series(days: int = 60) -> dict[str, float]:
    """
    마켓별 일별 equity를 로드하고 fill-forward 후 합산하여 반환.

    수정 이력:
    - v2 (2026-03-21): 통화 불일치 방지 및 허위 drawdown 알람 해소
      1. source="virtual_capital" 항목 제외 (US 미가동 시 $10K USD가 KRW와 혼합되던 버그)
      2. 마켓별 fill-forward 적용: 중간 날짜 데이터 공백으로 인한 peak→trough 오계산 방지
      3. 각 마켓은 첫 데이터 날짜~마지막 데이터 날짜 범위만 포함 (오래된 마켓 제외)
      4. 최소 2개 이상 유효 데이터 포인트가 있는 마켓만 포함
    """
    cutoff = (_utc_now().date() - timedelta(days=max(days, 30))).isoformat()

    # market → {day: equity} (마지막 값 유지)
    market_by_day: dict[str, dict[str, float]] = {}
    for market in ("btc", "kr", "us"):
        path = _equity_snapshot_path(market)
        if not path.exists():
            continue
        by_day: dict[str, float] = {}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                day = str(row.get("date") or "")[:10]
                if not day or day < cutoff:
                    continue
                # virtual_capital은 통화 단위가 달라 합산 대상에서 제외
                source = (row.get("metadata") or {}).get("source", "")
                if source == "virtual_capital":
                    continue
                equity = _safe_float(row.get("equity"), 0.0)
                if equity > 0:
                    by_day[day] = equity  # 같은 날이면 마지막 값 유지
        except Exception:
            continue
        if len(by_day) >= 2:  # 데이터 포인트가 2개 이상인 마켓만 포함
            market_by_day[market] = by_day

    if not market_by_day:
        return {}

    # 전체 날짜 집합
    all_days = sorted({d for series in market_by_day.values() for d in series})
    if not all_days:
        return {}

    # 마켓별 fill-forward: 첫 데이터~마지막 데이터 범위만 보간 (범위 밖 제외)
    filled: dict[str, dict[str, float]] = {}
    for market, by_day in market_by_day.items():
        sorted_days = sorted(by_day.keys())
        first_day = sorted_days[0]
        last_day = sorted_days[-1]
        last_val = 0.0
        mfilled: dict[str, float] = {}
        for day in all_days:
            if day < first_day or day > last_day:
                continue  # 이 마켓 활성 범위 밖이면 제외
            if day in by_day:
                last_val = by_day[day]
            if last_val > 0:
                mfilled[day] = last_val
        if mfilled:
            filled[market] = mfilled

    if not filled:
        return {}

    # 일별 합산
    combined: dict[str, float] = {}
    for day in all_days:
        day_sum = sum(m[day] for m in filled.values() if day in m)
        if day_sum > 0:
            combined[day] = round(day_sum, 6)
    return combined


def _compute_drawdown_from_equity(total_equity_by_day: dict[str, float]) -> float:
    if not total_equity_by_day:
        return 0.0
    peak = 0.0
    max_dd = 0.0
    for day in sorted(total_equity_by_day.keys()):
        eq = _safe_float(total_equity_by_day[day], 0.0)
        if eq <= 0:
            continue
        peak = max(peak, eq)
        if peak > 0:
            dd = eq / peak - 1.0
            max_dd = min(max_dd, dd)
    return round(max_dd, 6)


def build_risk_snapshot(lookback_days: int = 252) -> dict:
    positions = load_all_positions()
    proxy_map = {}
    for pos in positions:
        symbol = str(pos.get("symbol") or "").upper()
        proxy = _proxy_symbol(symbol)
        if symbol and proxy:
            proxy_map[symbol] = proxy

    returns_proxy = fetch_return_matrix(list(proxy_map.values()), lookback_days=lookback_days)
    returns_252d = {}
    for symbol, proxy in proxy_map.items():
        series = returns_proxy.get(proxy)
        if series:
            returns_252d[symbol] = series

    var_metrics = VaRModel(lookback_days=lookback_days).compute(positions, returns_252d) if returns_252d else {}
    total_equity_by_day = _load_latest_equity_series(days=90)
    snapshot = {
        "timestamp": _utc_now().isoformat(),
        "positions": positions,
        "returns_252d": returns_252d,
        "drawdown": _compute_drawdown_from_equity(total_equity_by_day),
        "var_95": _safe_float(var_metrics.get("var_95"), 0.0),
        "var_99": _safe_float(var_metrics.get("var_99"), 0.0),
        "cvar_95": _safe_float(var_metrics.get("cvar_95"), 0.0),
        "portfolio_vol": _safe_float(var_metrics.get("portfolio_vol"), 0.0),
        "diversification_ratio": _safe_float(var_metrics.get("diversification_ratio"), 1.0),
        "symbols": sorted(returns_252d.keys()),
    }
    return snapshot


def save_risk_snapshot(snapshot: dict) -> Path:
    path = _risk_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    out = build_risk_snapshot()
    path = save_risk_snapshot(out)
    print(path)
