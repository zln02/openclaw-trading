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


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


async def check_upbit() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        if not os.environ.get("UPBIT_ACCESS_KEY") or not os.environ.get("UPBIT_SECRET_KEY"):
            raise RuntimeError("UPBIT keys missing")
        import pyupbit

        price = pyupbit.get_current_price("KRW-BTC")
        if not price:
            raise RuntimeError("Upbit current price unavailable")
        return {"price": float(price)}

    return await asyncio.to_thread(_check)


async def check_supabase() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        # run_query_with_retry: 연결 끊김 시 자동 재연결 + 3회 재시도
        result = run_query_with_retry(
            lambda sb: sb.table("btc_position").select("id").limit(1).execute()
        )
        return {"rows": len(result.data or [])}

    return await asyncio.to_thread(_check)


async def check_kiwoom() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        app_key = os.environ.get("KIWOOM_MOCK_REST_API_APP_KEY", "")
        secret_key = os.environ.get("KIWOOM_MOCK_REST_API_SECRET_KEY", "")
        if not app_key or not secret_key:
            raise RuntimeError("Kiwoom mock credentials missing")
        return {"configured": True}

    return await asyncio.to_thread(_check)


async def check_dashboard() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        with socket.create_connection(("127.0.0.1", DASHBOARD_PORT), timeout=2):
            return {"port": DASHBOARD_PORT}

    return await asyncio.to_thread(_check)


async def check_cron_freshness() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        now = time.time()
        # 컨테이너 내부: cron 로그는 /app/logs/cron/ 에 마운트됨
        cron_log_dir = LOG_DIR / "cron"
        watched = [BTC_LOG, STOCK_TRADING_LOG, US_TRADING_LOG, DASHBOARD_LOG]
        if cron_log_dir.is_dir():
            watched += [
                cron_log_dir / "btc_trading.log",
                cron_log_dir / "stock_trading.log",
                cron_log_dir / "us_trading.log",
                cron_log_dir / "dashboard.log",
            ]
        last_seen = max(_safe_mtime(path) for path in watched)
        if last_seen <= 0:
            raise RuntimeError("No log activity found")
        age = int(now - last_seen)
        if age > 60 * 60 * 6:
            raise RuntimeError(f"Cron/log freshness stale: {age}s")
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
                log.warning("health snapshot persist failed", component=component, error=str(exc))


health_monitor = HealthMonitor()
