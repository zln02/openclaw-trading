#!/usr/bin/env python3
"""자동매매 시스템 자가 치유 에이전트.

5분마다 크론으로 실행되며:
1. 대시보드 헬스체크
2. 각 에이전트 로그 최근 갱신 시간 확인
3. 디스크 사용량 확인
4. 죽은 Docker 컨테이너 확인
5. 문제 발견 시 텔레그램 알림
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from common.config import LOG_DIR
from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import send_telegram

load_env()
log = get_logger("self_healer")
DEFAULT_ALERT_COOLDOWN_SECONDS = 30 * 60
ALERT_STATE_FILE = LOG_DIR / "self_healer_state.json"
DISK_WARN_THRESHOLD_PCT = 90
DISK_AUTO_CLEAN_THRESHOLD_PCT = 92
DISK_CLEANUP_TARGETS = (
    Path.home() / ".cache" / "pip",
    Path.home() / ".npm" / "_cacache",
    Path.home() / ".npm" / "_npx",
    Path.home() / ".local" / "share" / "pnpm" / "store",
)


def _issue_signature(issues: list[str]) -> str:
    payload = "\n".join(sorted(issues))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_alert_state(path: Path | None = None) -> dict:
    path = path or ALERT_STATE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"self-healer 상태 로드 실패: {exc}")
        return {}


def _save_alert_state(state: dict, path: Path | None = None) -> None:
    path = path or ALERT_STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.warning(f"self-healer 상태 저장 실패: {exc}")


def should_send_alert(
    issues: list[str],
    now_ts: float | None = None,
    cooldown_seconds: int = DEFAULT_ALERT_COOLDOWN_SECONDS,
    state_path: Path | None = None,
) -> bool:
    if not issues:
        return False
    now_ts = now_ts or time.time()
    state = _load_alert_state(state_path)
    signature = _issue_signature(issues)
    previous_signature = str(state.get("signature", ""))
    last_alert_ts = float(state.get("last_alert_ts", 0.0) or 0.0)

    if signature != previous_signature:
        return True
    return (now_ts - last_alert_ts) >= cooldown_seconds


def mark_alert_sent(
    issues: list[str],
    now_ts: float | None = None,
    state_path: Path | None = None,
) -> None:
    if not issues:
        return
    now_ts = now_ts or time.time()
    _save_alert_state(
        {
            "last_alert_ts": now_ts,
            "signature": _issue_signature(issues),
            "issue_count": len(issues),
        },
        state_path,
    )


def clear_alert_state(state_path: Path = ALERT_STATE_FILE) -> None:
    _save_alert_state({"last_alert_ts": 0.0, "signature": "", "issue_count": 0}, state_path)


def check_dashboard_health() -> dict:
    """대시보드 HTTP 헬스체크."""
    try:
        req = urllib.request.Request("http://localhost:8080/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": resp.status == 200, "status": resp.status}
    except Exception as e:
        log.error(f"대시보드 헬스체크 실패: {e}", exc_info=True)
        return {"ok": False, "error": "healthcheck_failed"}


def check_log_freshness(max_stale_minutes: int = 30) -> list[dict]:
    """각 에이전트 로그 파일의 최근 갱신 시간 확인."""
    issues: list[dict] = []
    log_files = {
        "btc": LOG_DIR / "btc_trading.log",
        "kr": LOG_DIR / "stock_trading.log",
        "us": LOG_DIR / "us_trading.log",
    }
    now = time.time()
    for name, path in log_files.items():
        try:
            if not path.exists():
                issues.append({"agent": name, "missing": True, "path": str(path)})
                continue
            stale_min = (now - path.stat().st_mtime) / 60
            if stale_min > max_stale_minutes:
                issues.append(
                    {
                        "agent": name,
                        "stale_minutes": round(stale_min),
                        "path": str(path),
                    }
                )
        except Exception as e:
            log.warning(f"{name} 로그 신선도 확인 실패: {e}")
    return issues


def check_disk_usage(threshold_pct: int = 90) -> dict | None:
    """디스크 사용량 확인."""
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used_pct = round((1 - free / total) * 100)
        if used_pct >= threshold_pct:
            return {
                "used_pct": used_pct,
                "free_gb": round(free / (1024**3), 1),
            }
    except Exception as e:
        log.warning(f"디스크 확인 실패: {e}")
    return None


def cleanup_disk_space(targets: tuple[Path, ...] = DISK_CLEANUP_TARGETS) -> dict:
    """안전한 캐시 디렉터리만 정리해 디스크 여유 공간을 회수한다."""
    reclaimed_bytes = 0
    removed: list[str] = []
    errors: list[str] = []

    for path in targets:
        try:
            if not path.exists():
                continue
            if path.is_dir():
                size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                shutil.rmtree(path)
            else:
                size = path.stat().st_size
                path.unlink()
            reclaimed_bytes += size
            removed.append(str(path))
        except Exception as exc:
            errors.append(f"{path}: {exc}")

    reclaimed_gb = round(reclaimed_bytes / (1024**3), 2)
    if removed:
        log.info(f"디스크 자동 정리 수행: {len(removed)}개, 약 {reclaimed_gb}GB 회수")
    for err in errors:
        log.warning(f"디스크 자동 정리 실패: {err}")

    return {
        "reclaimed_bytes": reclaimed_bytes,
        "reclaimed_gb": reclaimed_gb,
        "removed": removed,
        "errors": errors,
    }


def _format_disk_issue(disk: dict, cleanup: dict | None = None) -> str:
    bucket = max(DISK_WARN_THRESHOLD_PCT, int(disk["used_pct"] // 5 * 5))
    message = f"💾 디스크 사용률 {bucket}%+ 구간 (남은: {disk['free_gb']}GB)"
    if cleanup and cleanup.get("reclaimed_bytes", 0) > 0:
        message += f" | 자동정리 {cleanup['reclaimed_gb']}GB"
    return message


def check_docker_containers() -> list[str]:
    """죽은 Docker 컨테이너 확인."""
    issues: list[str] = []
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        for line in result.stdout.strip().splitlines():
            if "openclaw-" in line and "Exited" in line:
                issues.append(line.strip())
    except Exception as e:
        log.warning(f"Docker 확인 실패: {e}")
    return issues


def send_alert(message: str) -> None:
    """텔레그램 알림 전송."""
    try:
        send_telegram(f"🔧 자가치유 알림\n{message}")
    except Exception as e:
        log.warning(f"알림 전송 실패: {e}")


def collect_issues() -> list[str]:
    """현재 시스템 상태를 점검하고 경고 목록을 수집한다."""
    issues: list[str] = []

    dash = check_dashboard_health()
    if not dash.get("ok"):
        issues.append(f"❌ 대시보드 다운: {dash}")

    stale = check_log_freshness(max_stale_minutes=30)
    for item in stale:
        if item.get("missing"):
            issues.append(f"📄 {item['agent']} 로그 없음: {item['path']}")
        else:
            issues.append(f"⏰ {item['agent']} 에이전트 {item['stale_minutes']}분 동안 무응답")

    disk = check_disk_usage(threshold_pct=DISK_WARN_THRESHOLD_PCT)
    if disk:
        cleanup = None
        if disk["used_pct"] >= DISK_AUTO_CLEAN_THRESHOLD_PCT:
            cleanup = cleanup_disk_space()
            disk = check_disk_usage(threshold_pct=DISK_WARN_THRESHOLD_PCT)
        if disk:
            issues.append(_format_disk_issue(disk, cleanup))

    dead = check_docker_containers()
    for container in dead:
        issues.append(f"🐳 컨테이너 중지됨: {container}")

    try:
        from quant.risk.correlation_monitor import check_concentration_risk

        corr = check_concentration_risk()
        if corr.get("risk_level") == "HIGH":
            issues.append(f"📊 포트폴리오 집중도 HIGH: {corr['long_count']}개 시장 동시 LONG")
    except Exception as e:
        log.warning(f"상관관계 체크 실패: {e}")

    try:
        import psutil

        mem = psutil.virtual_memory()
        if mem.percent > 85:
            issues.append(f"🧠 메모리 사용률 {mem.percent}% (>85%)")
    except ImportError:
        pass

    try:
        from common.supabase_client import get_supabase

        sb = get_supabase()
        if not sb:
            raise RuntimeError("Supabase client unavailable")
        sb.table("trade_executions").select("trade_id").limit(1).execute()
    except Exception as e:
        issues.append(f"🗄️ Supabase 연결 실패: {e}")

    return issues


def run() -> None:
    """자가 치유 메인 루프."""
    issues = collect_issues()
    if not issues:
        clear_alert_state()
        log.info("헬스체크 정상")
        return

    message = "\n".join(issues)
    log.warning(f"문제 발견:\n{message}")
    if should_send_alert(issues):
        send_alert(message)
        mark_alert_sent(issues)
        return

    log.info("중복 self-healer 알림 억제")


if __name__ == "__main__":
    run()
