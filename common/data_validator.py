"""Market data validation and stale-data fallback helpers."""
from __future__ import annotations

import time
from typing import Any

from common.logger import get_logger
from common.telegram import send_telegram

log = get_logger("data_validator")


class DataValidator:
    """Validate live market data before it reaches trading logic."""

    VALID_RANGES = {
        "fg": (0, 100),
        "fg_value": (0, 100),
        "rsi": (0, 100),
        "rsi_d": (0, 100),
        "bb": (0, 100),
        "bb_pct": (0, 100),
        "trend": (0, 100),
        "trend_score": (0, 100),
        "volume": (0, 200),
        "volume_score": (0, 200),
        "vol_ratio": (0, 200),
        "vol_ratio_d": (0, 200),
        "funding": (-1, 1),
        "funding_rate": (-1, 1),
        "btc_price": (10_000_000, 500_000_000),
        "price": (0, 1_000_000_000),
    }

    def __init__(self) -> None:
        self.cache: dict[str, Any] = {}
        self.timestamps: dict[str, float] = {}

    def validate(self, data: dict[str, Any] | None, *, prefix: str = "", alert: bool = True) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {}

        clean: dict[str, Any] = {}
        alerts: list[str] = []

        for key, value in data.items():
            scoped_key = f"{prefix}.{key}" if prefix else key
            rule_key = key if key in self.VALID_RANGES else scoped_key

            if isinstance(value, dict):
                clean[key] = self.validate(value, prefix=scoped_key, alert=alert)
                continue

            if rule_key in self.VALID_RANGES:
                min_val, max_val = self.VALID_RANGES[rule_key]
                if value is None or not self._is_in_range(value, min_val, max_val):
                    cached = self.cache.get(scoped_key, self.cache.get(key))
                    clean[key] = cached
                    alerts.append(f"{scoped_key}={value} invalid -> cached {cached}")
                    continue

            clean[key] = value
            self.cache[scoped_key] = value
            self.timestamps[scoped_key] = time.time()

        if alerts and alert:
            msg = "🔍 Data Validation Alerts:\n" + "\n".join(alerts[:10])
            try:
                send_telegram(msg)
            except Exception as exc:
                log.warning("validation alert send failed", error=str(exc))
            log.warning("market data validation fallback used", alerts=alerts[:10])

        return clean

    def is_stale(self, key: str, max_age_seconds: int = 300) -> bool:
        ts = self.timestamps.get(key)
        if ts is None:
            return True
        return time.time() - ts > max_age_seconds

    @staticmethod
    def _is_in_range(value: Any, min_val: float, max_val: float) -> bool:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return False
        return min_val <= num <= max_val


validator = DataValidator()
