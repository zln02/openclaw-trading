"""Centralized health monitoring for OpenClaw services."""
from __future__ import annotations

import asyncio
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any

from common.config import DASHBOARD_PORT
from common.logger import get_logger
from common.supabase_client import get_supabase, run_query_with_retry
from common.telegram import send_telegram

log = get_logger("health")
_HEALTH_SNAPSHOT_TABLE_MISSING = False


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
        app_key = os.environ.get("KIWOOM_MOCK_REST_API_APP_KEY", "")
        secret_key = os.environ.get("KIWOOM_MOCK_REST_API_SECRET_KEY", "")
        if not app_key or not secret_key:
            raise RuntimeError("키움 모의투자 API 키가 설정되지 않았습니다 (KIWOOM_MOCK_REST_API_APP_KEY / SECRET_KEY)")
        return {"configured": True}

    return await asyncio.to_thread(_check)


async def check_dashboard() -> dict[str, Any]:
    def _check() -> dict[str, Any]:
        try:
            with socket.create_connection(("127.0.0.1", DASHBOARD_PORT), timeout=2):
                return {"port": DASHBOARD_PORT}
        except OSError as exc:
            raise RuntimeError(f"대시보드 포트 {DASHBOARD_PORT} 연결 실패: {exc}") from exc

    return await asyncio.to_thread(_check)


def _last_btc_trade_ts(supabase: Any) -> datetime | None:
    """btc_trades 테이블의 마지막 timestamp (HOLD 포함, 매 사이클 기록)."""
    res = (
        supabase.table("btc_trades")
        .select("timestamp")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    raw = rows[0].get("timestamp")
    if not raw:
        return None
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


async def check_cron_freshness() -> dict[str, Any]:
    """BTC 매매 사이클 신선도 검사.

    신호원: supabase `btc_trades.timestamp` (매 사이클 HOLD 포함 기록).
    BTC만 critical 신호로 사용. KR/US는 BUY/SELL만 기록되어 사이클 신호로 부적합 →
    별 PR에서 heartbeat 테이블 도입 시 추가 검사.
    """

    def _check() -> dict[str, Any]:
        supabase = get_supabase()
        if supabase is None:
            raise RuntimeError("Supabase 클라이언트 미초기화")

        now_utc = datetime.now(timezone.utc)
        last_ts = _last_btc_trade_ts(supabase)
        if last_ts is None:
            raise RuntimeError("btc_trades 테이블에 데이터가 없습니다 (BTC 에이전트 미실행)")

        age_min = (now_utc - last_ts).total_seconds() / 60
        if age_min > 30:
            raise RuntimeError(
                f"BTC 사이클 정체 — btc_trades {round(age_min)}분간 갱신 안됨 (cron/사이클 정지 의심)"
            )

        return {
            "btc": {"age_minutes": round(age_min)},
            "kr": {"signal": "not_tracked", "note": "trade_executions BUY/SELL only"},
            "us": {"signal": "not_tracked", "note": "us_trade_executions BUY/SELL only"},
            "source": "supabase.btc_trades",
        }

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
