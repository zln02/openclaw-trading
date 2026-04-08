"""Centralized health monitoring for OpenClaw services."""
from __future__ import annotations

import asyncio
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.config import BTC_LOG, DASHBOARD_PORT, DASHBOARD_LOG, LOG_DIR, STOCK_TRADING_LOG, US_TRADING_LOG
from common.logger import get_logger
from common.supabase_client import get_supabase, run_query_with_retry
from common.telegram import send_telegram

log = get_logger("health")
_HEALTH_SNAPSHOT_TABLE_MISSING = False


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


async def check_upbit() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        if not os.environ.get("UPBIT_ACCESS_KEY") or not os.environ.get("UPBIT_SECRET_KEY"):
            raise RuntimeError("업비트 API 키가 설정되지 않았습니다 (UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY)")
        import pyupbit

        price = pyupbit.get_current_price("KRW-BTC")
        if not price:
            raise RuntimeError("업비트 현재가 조회 실패 (응답 없음)")
        return {"price": float(price)}

    return await asyncio.to_thread(_check)


async def check_supabase() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        result = run_query_with_retry(
            lambda sb: sb.table("btc_position").select("id").limit(1).execute()
        )
        if result is None:
            raise RuntimeError("Supabase 연결 실패 (응답 없음)")
        return {"rows": len(result.data or [])}

    try:
        return await asyncio.to_thread(_check)
    except Exception as exc:
        raise RuntimeError(f"Supabase 연결 오류: {exc}") from exc


async def check_kiwoom() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        from common.kiwoom_env import get_kiwoom_credentials
        try:
            creds = get_kiwoom_credentials()
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        return {
            "configured": True,
            "mode": "mock" if creds.use_mock else "prod",
        }

    return await asyncio.to_thread(_check)


async def check_dashboard() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        try:
            with socket.create_connection(("127.0.0.1", DASHBOARD_PORT), timeout=2):
                return {"port": DASHBOARD_PORT}
        except OSError as exc:
            raise RuntimeError(f"대시보드 포트 {DASHBOARD_PORT} 연결 실패: {exc}") from exc

    return await asyncio.to_thread(_check)


async def check_cron_freshness() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        now = time.time()
        cron_log_dir = LOG_DIR / "cron"
        watched = [BTC_LOG, STOCK_TRADING_LOG, US_TRADING_LOG, DASHBOARD_LOG]
        if cron_log_dir.is_dir():
            watched += [
                cron_log_dir / "btc_trading.log",
                cron_log_dir / "stock_trading.log",
                cron_log_dir / "us_trading.log",
                cron_log_dir / "dashboard.log",
            ]
        mtimes = [_safe_mtime(p) for p in watched]
        last_seen = max(mtimes) if mtimes else 0.0
        if last_seen <= 0:
            raise RuntimeError("에이전트 로그 파일을 찾을 수 없습니다 (cron 미실행 또는 로그 경로 오류)")
        age = int(now - last_seen)
        if age > 60 * 60 * 14:
            hours = age // 3600
            raise RuntimeError(f"에이전트 로그가 {hours}시간 동안 갱신되지 않았습니다 (cron 중단 의심)")
        return {"age_seconds": age, "log_dir": str(LOG_DIR)}

    return await asyncio.to_thread(_check)


class HealthMonitor:
    COMPONENTS = {
        "upbit_api": {"check": check_upbit, "critical": True},
        "supabase": {"check": check_supabase, "critical": True},
        "kiwoom": {"check": check_kiwoom, "critical": False},
        "dashboard": {"check": check_dashboard, "critical": False},
        "cron_jobs": {"check": check_cron_freshness, "critical": True},
    }
    # Telegram 알림 쿨다운: 컴포넌트별 마지막 발송 시각
    _ALERT_COOLDOWN_SEC = 30 * 60  # 30분
    _last_alert: dict[str, float] = {}

    async def run_checks(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        supabase = get_supabase()
        now = time.time()

        for name, config in self.COMPONENTS.items():
            started = time.time()
            try:
                details = await config["check"]()
                latency = int((time.time() - started) * 1000)
                results[name] = {"status": "healthy", "latency_ms": latency, "details": details}
                # 복구 시 쿨다운 초기화
                self._last_alert.pop(name, None)
            except Exception as exc:
                results[name] = {"status": "down", "error": str(exc)}
                log.error("health check failed", component=name, error=str(exc))
                if config.get("critical"):
                    last = self._last_alert.get(name, 0)
                    if now - last >= self._ALERT_COOLDOWN_SEC:
                        try:
                            await asyncio.to_thread(send_telegram, f"🚨 CRITICAL: {name} is DOWN — {str(exc)[:200]}")
                            self._last_alert[name] = now
                        except Exception:
                            pass

        if supabase:
            await asyncio.to_thread(self._persist_snapshots, supabase, results)

        all_healthy = all(item["status"] == "healthy" for item in results.values())
        return {
            "status": "ok" if all_healthy else "degraded",
            "components": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _persist_snapshots(supabase: Any, results: dict[str, Any]) -> None:
        global _HEALTH_SNAPSHOT_TABLE_MISSING
        if _HEALTH_SNAPSHOT_TABLE_MISSING:
            return

        for component, result in results.items():
            try:
                supabase.table("health_snapshots").insert(
                    {
                        "component": component,
                        "status": result["status"],
                        "details": result,
                        "latency_ms": result.get("latency_ms"),
                    }
                ).execute()
            except Exception as exc:
                if "PGRST205" in str(exc) and "health_snapshots" in str(exc):
                    _HEALTH_SNAPSHOT_TABLE_MISSING = True
                    log.warning("health snapshot persistence disabled", error=str(exc))
                    return
                log.warning("health snapshot persist failed", component=component, error=str(exc))


health_monitor = HealthMonitor()
