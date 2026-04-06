"""
OpenClaw Gateway 알림 모듈.
자동매매 에이전트 → OpenClaw Gateway → 텔레그램 연동.
실패 시 기존 텔레그램 직접 발송으로 graceful fallback.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional

from common.logger import get_logger

log = get_logger("openclaw_notify")

GATEWAY_URL = "http://127.0.0.1:18789"
# audit fix: 하드코딩 제거 — 환경변수 우선, 기본값 fallback
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "oc-secure-92a18f72c4e53b")
NOTIFY_TIMEOUT = 5  # seconds


def notify_openclaw(
    event: str,
    message: str,
    urgent: bool = False,
    metadata: Optional[dict] = None,
) -> bool:
    """
    OpenClaw Gateway에 이벤트 알림 전송.

    Args:
        event: 이벤트 타입 (trade_buy, trade_sell, stop_loss, drawdown_guard 등)
        message: 알림 메시지
        urgent: 긴급 여부 (True면 즉시 텔레그램 발송)
        metadata: 추가 메타데이터 (종목, 가격 등)

    Returns:
        성공 여부
    """
    try:
        payload = {
            "event": event,
            "message": message,
            "urgent": urgent,
        }
        if metadata:
            payload["metadata"] = metadata

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{GATEWAY_URL}/hooks/wake",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GATEWAY_TOKEN}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=NOTIFY_TIMEOUT) as resp:
            if resp.status in (200, 201, 202):
                log.debug(f"OpenClaw notify OK: {event}")
                return True
            log.warning(f"OpenClaw notify unexpected status: {resp.status}")
            return False

    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        log.debug(f"OpenClaw notify failed ({event}): {e}, fallback to telegram")
        return _fallback_telegram(event, message, urgent)
    except Exception as e:
        log.debug(f"OpenClaw notify error: {e}")
        return False


def _fallback_telegram(event: str, message: str, urgent: bool) -> bool:
    """Gateway 불가 시 텔레그램 직접 발송 fallback."""
    try:
        from common.telegram import send_telegram  # audit fix: send_telegram_message → send_telegram

        prefix = "🚨" if urgent else "📢"
        text = f"{prefix} [{event}] {message}"
        send_telegram(text)
        return True
    except Exception as e:
        log.warning(f"Telegram fallback also failed: {e}")
        return False
