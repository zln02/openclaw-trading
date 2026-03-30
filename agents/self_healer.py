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

import os
import subprocess
import time
import urllib.request

from common.config import LOG_DIR
from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import send_telegram

load_env()
log = get_logger("self_healer")


def check_dashboard_health() -> dict:
    """대시보드 HTTP 헬스체크."""
    try:
        req = urllib.request.Request("http://localhost:8080/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": resp.status == 200, "status": resp.status}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


def run() -> None:
    """자가 치유 메인 루프."""
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

    disk = check_disk_usage(threshold_pct=90)
    if disk:
        issues.append(f"💾 디스크 {disk['used_pct']}% 사용 (남은: {disk['free_gb']}GB)")

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
        sb.table("trade_executions").select("id").limit(1).execute()
    except Exception as e:
        issues.append(f"🗄️ Supabase 연결 실패: {e}")

    if issues:
        message = "\n".join(issues)
        log.warning(f"문제 발견:\n{message}")
        send_alert(message)
    else:
        log.info("헬스체크 정상")


if __name__ == "__main__":
    run()
