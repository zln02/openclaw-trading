"""Param Optimizer — IC/IR + Attribution 결과 자동 파라미터 반영 (Phase Level 5).

트리거: 매주 일요일 23:30 (signal_evaluator 완료 후)

반영 규칙 (완전 자율, 텔레그램 알림만):
- IR < SIGNAL_IC_IR_MIN (0.3) → 해당 신호 disable
- best_params.json 존재 → 에이전트 파라미터 적용
- 주간 win_rate < 0.40 → stop_loss 민감도 증가 + 포지션 축소
- 주간 sharpe > 1.5 → 포지션 한도 허용 상향

실행:
    python -m quant.param_optimizer [--dry-run]
    scripts/run_param_optimizer.sh
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config import (
    BRAIN_PATH,
    SIGNAL_IC_IR_MIN,
    WORKSPACE,
)
from common.env_loader import load_env
from common.logger import get_logger
from common.metrics import calc_sharpe, calc_trade_pnl, calc_win_rate
from common.supabase_client import get_supabase
from common.telegram import Priority, send_telegram

load_env()
log = get_logger("param_optimizer")

# 경로 상수
_WEIGHTS_PATH = BRAIN_PATH / "signal-ic" / "weights.json"
_BEST_PARAMS_PATH = BRAIN_PATH / "alpha" / "best_params.json"
_AGENT_PARAMS_PATH = BRAIN_PATH / "agent_params.json"

# 자율 조정 임계값
_WIN_RATE_LOW = 0.40      # 이 이하이면 방어 모드
_SHARPE_HIGH = 1.5        # 이 이상이면 공격 허용
_STOP_LOSS_TIGHTEN = 0.8  # stop_loss × 이 값 (더 타이트하게)
_POS_SIZE_REDUCE = 0.85   # invest_ratio × 이 값
_POS_SIZE_INCREASE = 1.10 # invest_ratio × 이 값 (sharpe 높을 때)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


# ── Performance stats from Supabase ───────────────────────────────────────────

def _load_weekly_stats(supabase, lookback_days: int = 7) -> Dict[str, Any]:
    """지난 7일 trade_executions에서 승률/샤프 계산."""
    if not supabase:
        return {}
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=lookback_days)
    ).date().isoformat()

    try:
        rows = (
            supabase.table("trade_executions")
            .select("result,trade_type,price,entry_price")
            .eq("result", "CLOSED")
            .eq("trade_type", "SELL")
            .gte("created_at", cutoff)
            .execute()
            .data or []
        )
    except Exception as exc:
        log.warning("weekly stats 로드 실패", error=exc)
        return {}

    if not rows:
        return {"n_trades": 0}

    pnls: List[float] = []
    for r in rows:
        pnl = calc_trade_pnl(r, market="kr")
        if pnl is not None:
            pnls.append(pnl)

    if not pnls:
        return {"n_trades": len(rows)}

    n = len(pnls)
    win_rate = calc_win_rate(rows, market="kr")
    avg_pnl = sum(pnls) / n if n > 0 else 0.0
    sharpe = calc_sharpe(pnls)

    return {
        "n_trades": n,
        "win_rate": round(win_rate, 4),
        "avg_pnl": round(avg_pnl, 4),
        "sharpe": round(sharpe, 4),
        "pnls": pnls,
    }


# ── Signal weights management ──────────────────────────────────────────────────

def _disable_low_ir_signals(dry_run: bool = False) -> List[str]:
    """IC weights에서 IR 기준 미달 신호 disable."""
    if not _WEIGHTS_PATH.exists():
        log.warning("weights.json 없음 — 신호 disable 스킵")
        return []

    try:
        payload = json.loads(_WEIGHTS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("weights.json 로드 실패", error=exc)
        return []

    # signal_evaluator가 저장한 최신 IC 리포트에서 IR 확인
    ic_dir = BRAIN_PATH / "signal-ic"
    report_files = sorted(ic_dir.glob("20*.json"), reverse=True)
    if not report_files:
        return []

    try:
        report = json.loads(report_files[0].read_text(encoding="utf-8"))
    except Exception:
        return []

    disabled: List[str] = []
    weights = payload.get("weights", {})

    for sig in report.get("signals", []):
        name = sig.get("signal", "")
        ir = _safe_float(sig.get("ir"), 0.0)
        if name in weights and abs(ir) < SIGNAL_IC_IR_MIN:
            disabled.append(name)
            if not dry_run:
                del weights[name]

    if disabled and not dry_run:
        # 재정규화
        total = sum(v for v in weights.values() if v > 0)
        if total > 0:
            payload["weights"] = {k: round(v / total, 6) for k, v in weights.items() if v > 0}
        payload["param_optimizer_updated"] = datetime.now(timezone.utc).isoformat()
        _WEIGHTS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return disabled


# ── Agent params management ────────────────────────────────────────────────────

def _load_agent_params() -> Dict[str, Any]:
    if _AGENT_PARAMS_PATH.exists():
        try:
            return json.loads(_AGENT_PARAMS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_agent_params(params: Dict[str, Any]) -> None:
    _AGENT_PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    params["updated"] = datetime.now(timezone.utc).isoformat()
    _AGENT_PARAMS_PATH.write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _apply_best_params(dry_run: bool = False) -> Optional[Dict[str, Any]]:
    """alpha_researcher의 best_params.json → agent_params.json에 반영."""
    if not _BEST_PARAMS_PATH.exists():
        return None
    try:
        best = json.loads(_BEST_PARAMS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not best.get("improved", False):
        return None  # 기존보다 개선 안된 경우 적용 안 함

    current = _load_agent_params()
    new_params = best.get("params", {})

    changes: Dict[str, Any] = {}
    for k, v in new_params.items():
        old_v = current.get(k)
        if old_v != v:
            changes[k] = {"old": old_v, "new": v}
            current[k] = v

    if not changes:
        return None

    if not dry_run:
        _save_agent_params(current)

    return changes


def _apply_performance_adjustments(
    stats: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """win_rate / sharpe 기반 리스크 파라미터 자동 조정."""
    if not stats:
        return {}

    current = _load_agent_params()
    changes: Dict[str, Any] = {}

    win_rate = stats.get("win_rate", 0.5)
    sharpe = stats.get("sharpe", 0.0)
    n_trades = stats.get("n_trades", 0)

    if n_trades < 3:
        log.info("거래 건수 부족 — 자동 조정 스킵", n_trades=n_trades)
        return {}

    if win_rate < _WIN_RATE_LOW:
        # 방어 모드: stop_loss 더 타이트 + 포지션 축소
        old_sl = current.get("stop_loss", -0.025)
        new_sl = round(old_sl * _STOP_LOSS_TIGHTEN, 4)   # 절대값 감소 = 더 타이트
        old_ir = current.get("invest_ratio", 0.25)
        new_ir = round(old_ir * _POS_SIZE_REDUCE, 4)
        if new_sl != old_sl:
            changes["stop_loss"] = {"old": old_sl, "new": new_sl}
            current["stop_loss"] = new_sl
        if new_ir != old_ir:
            changes["invest_ratio"] = {"old": old_ir, "new": new_ir}
            current["invest_ratio"] = new_ir
        log.info(
            "방어 모드 적용",
            win_rate=win_rate,
            stop_loss=f"{old_sl}→{new_sl}",
            invest_ratio=f"{old_ir}→{new_ir}",
        )

    elif sharpe > _SHARPE_HIGH:
        # 공격 허용: 포지션 한도 상향
        old_ir = current.get("invest_ratio", 0.25)
        new_ir = round(min(old_ir * _POS_SIZE_INCREASE, 0.40), 4)
        if new_ir != old_ir:
            changes["invest_ratio"] = {"old": old_ir, "new": new_ir}
            current["invest_ratio"] = new_ir
        log.info("공격 허용 모드", sharpe=sharpe, invest_ratio=f"{old_ir}→{new_ir}")

    if changes and not dry_run:
        _save_agent_params(current)

    return changes


# ── ParamOptimizer ─────────────────────────────────────────────────────────────

class ParamOptimizer:
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client or get_supabase()

    def _backup_params(self) -> None:
        """현재 agent_params.json을 날짜 스탬프 파일로 백업."""
        src = _AGENT_PARAMS_PATH
        if not src.exists():
            return
        dst = _AGENT_PARAMS_PATH.parent / f"agent_params_backup_{datetime.now(timezone.utc).date().isoformat()}.json"
        try:
            shutil.copy2(src, dst)
            log.info("파라미터 백업 완료", backup=str(dst))
        except Exception as exc:
            log.warning("파라미터 백업 실패", error=exc)

    def rollback_params(self, backup_date: str | None = None) -> bool:
        """가장 최근 또는 지정 날짜의 백업으로 파라미터를 롤백.

        Args:
            backup_date: 'YYYY-MM-DD' 형식. None이면 가장 최근 백업 사용.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        if backup_date:
            src = _AGENT_PARAMS_PATH.parent / f"agent_params_backup_{backup_date}.json"
        else:
            backups = sorted(
                _AGENT_PARAMS_PATH.parent.glob("agent_params_backup_*.json"), reverse=True
            )
            if not backups:
                log.warning("롤백할 백업 없음")
                return False
            src = backups[0]

        if not src.exists():
            log.warning("백업 파일 없음", path=str(src))
            return False

        try:
            shutil.copy2(src, _AGENT_PARAMS_PATH)
            log.info("파라미터 롤백 완료", source=src.name)
            return True
        except Exception as exc:
            log.warning("파라미터 롤백 실패", error=exc)
            return False

    def run(self, dry_run: bool = False, lookback_days: int = 7) -> Dict[str, Any]:
        log.info("param_optimizer 시작", dry_run=dry_run)

        # 변경 전 백업
        if not dry_run:
            self._backup_params()

        # 1. 저품질 신호 disable
        disabled_signals = _disable_low_ir_signals(dry_run=dry_run)

        # 2. best_params 적용
        param_changes = _apply_best_params(dry_run=dry_run)

        # 3. 성과 기반 자동 조정
        stats = _load_weekly_stats(self.supabase, lookback_days=lookback_days)
        perf_changes = _apply_performance_adjustments(stats, dry_run=dry_run)

        # Attribution 분석 실행
        attribution_result: Dict[str, Any] = {}
        try:
            from quant.portfolio.attribution import WeeklyAttributionRunner
            runner = WeeklyAttributionRunner(supabase_client=self.supabase)
            attribution_result = runner.run(lookback_days=lookback_days, dry_run=dry_run)
        except Exception as exc:
            log.warning("attribution 실행 실패", error=exc)

        # 텔레그램 요약 알림
        self._send_summary(
            disabled_signals=disabled_signals,
            param_changes=param_changes,
            perf_changes=perf_changes,
            stats=stats,
            attribution_result=attribution_result,
            dry_run=dry_run,
        )

        return {
            "disabled_signals": disabled_signals,
            "param_changes": param_changes or {},
            "perf_changes": perf_changes,
            "weekly_stats": {
                k: v for k, v in stats.items() if k != "pnls"
            },
            "attribution_status": attribution_result.get("status", "N/A"),
            "dry_run": dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _send_summary(
        self,
        disabled_signals: List[str],
        param_changes: Optional[Dict],
        perf_changes: Dict,
        stats: Dict,
        attribution_result: Dict,
        dry_run: bool,
    ) -> None:
        lines = [
            f"⚙️ <b>주간 파라미터 자동 업데이트</b>{'[DRY-RUN]' if dry_run else ''}",
            "",
        ]

        # 성과 요약
        n = stats.get("n_trades", 0)
        if n > 0:
            lines.append(
                f"📈 주간 성과: {n}건 | 승률={stats.get('win_rate', 0)*100:.1f}% "
                f"| 샤프={stats.get('sharpe', 0):.2f} | 평균PnL={stats.get('avg_pnl', 0):+.2f}%"
            )
        else:
            lines.append("📈 주간 성과 데이터 없음")

        # 신호 disable
        if disabled_signals:
            lines.append(f"\n🔕 비활성화 신호 (IR < {SIGNAL_IC_IR_MIN}): {', '.join(disabled_signals)}")

        # 파라미터 변경
        if param_changes:
            lines.append("\n🎯 알파 파라미터 업데이트:")
            for k, v in param_changes.items():
                lines.append(f"  {k}: {v['old']} → {v['new']}")

        # 성과 기반 조정
        if perf_changes:
            lines.append("\n⚠️ 성과 기반 리스크 조정:")
            for k, v in perf_changes.items():
                lines.append(f"  {k}: {v['old']} → {v['new']}")

        # Attribution 요약
        attr_n = attribution_result.get("n_trades", 0)
        if attr_n > 0:
            lines.append(f"\n📊 Attribution: {attr_n}건 분석 완료")
            if attribution_result.get("weights_updated"):
                lines.append("  🔄 팩터 가중치 자동 조정됨")

        try:
            send_telegram("\n".join(lines), priority=Priority.INFO)
        except Exception as exc:
            log.warning("telegram 알림 실패", error=exc)


# ── load_agent_params (에이전트에서 사용) ─────────────────────────────────────

def load_best_params() -> Dict[str, Any]:
    """에이전트 시작 시 brain/agent_params.json 로드.

    Returns:
        dict of param overrides (empty dict if no file)
    """
    if _AGENT_PARAMS_PATH.exists():
        try:
            params = json.loads(_AGENT_PARAMS_PATH.read_text(encoding="utf-8"))
            params.pop("updated", None)
            return params
        except Exception:
            pass
    return {}


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli() -> int:
    p = argparse.ArgumentParser(description="Param optimizer — 자율 파라미터 조정")
    p.add_argument("--dry-run", action="store_true", help="저장/알림 없이 출력만")
    p.add_argument("--lookback", type=int, default=7, help="성과 분석 기간 (일)")
    args = p.parse_args()

    optimizer = ParamOptimizer()
    result = optimizer.run(dry_run=args.dry_run, lookback_days=args.lookback)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
