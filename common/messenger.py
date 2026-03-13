"""Unified multi-channel messaging facade."""
from __future__ import annotations

import asyncio
import os
from typing import Any

import requests

from common.logger import get_logger
from common.telegram import Priority, send_telegram

log = get_logger("messenger")


class TelegramChannel:
    @staticmethod
    async def send(event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        priority = Priority.URGENT if event_type in {"circuit_breaker", "health_down"} else Priority.IMPORTANT
        await asyncio.to_thread(send_telegram, message, priority=priority)


class WebSocketChannel:
    @staticmethod
    async def send(event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        log.info("dashboard ws broadcast queued", event_type=event_type, has_data=bool(data))


class ExpoPushChannel:
    @staticmethod
    async def send(event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        log.info("expo push broadcast queued", event_type=event_type, has_data=bool(data))


class WebhookChannel:
    @staticmethod
    async def send(event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        urls = [u.strip() for u in os.environ.get("OPENCLAW_WEBHOOK_URLS", "").split(",") if u.strip()]
        if not urls:
            return

        payload = {"event_type": event_type, "message": message, "data": data or {}}
        for url in urls:
            try:
                await asyncio.to_thread(requests.post, url, json=payload, timeout=5)
            except Exception as exc:
                log.warning("webhook broadcast failed", url=url, error=str(exc))


class UnifiedMessenger:
    CHANNELS = {
        "telegram": TelegramChannel,
        "dashboard_ws": WebSocketChannel,
        "expo_push": ExpoPushChannel,
        "webhook": WebhookChannel,
    }

    async def broadcast(
        self,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
        channels: list[str] | None = None,
    ) -> None:
        targets = channels or list(self.CHANNELS.keys())
        for channel_name in targets:
            channel = self.CHANNELS.get(channel_name)
            if channel is None:
                continue
            try:
                await channel.send(event_type, message, data)
            except Exception as exc:
                log.error("messenger channel failed", channel=channel_name, error=str(exc))


messenger = UnifiedMessenger()
