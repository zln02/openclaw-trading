"""Intelligent alert manager (Phase 18)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from common.cache import get_cached, set_cached
from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import send_telegram
from common.utils import safe_float as _safe_float

load_env()
log = get_logger("alert_manager")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pct_to_decimal(v: float) -> float:
    # Accept -3 (percent) or -0.03 (decimal)
    if abs(v) > 1.0:
        return v / 100.0
    return v


@dataclass
class Alert:
    level: str
    key: str
    title: str
    message: str
    recommendation: str
    metadata: dict
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlertConfig:
    drawdown_threshold: float = -0.03
    var_limit: float = 0.025
    corr_shift_threshold: float = 0.30
    volume_spike_threshold: float = 2.0
    cooldown_seconds: int = 600


class AlertManager:
    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()

    def _seen_key(self, key: str) -> str:
        return f"alerts:cooldown:{key}"

    def _should_emit(self, key: str) -> bool:
        return get_cached(self._seen_key(key)) is None

    def _mark_emitted(self, key: str) -> None:
        set_cached(self._seen_key(key), True, ttl=max(int(self.config.cooldown_seconds), 1))

    def evaluate(self, snapshot: dict) -> list[dict]:
        drawdown = _pct_to_decimal(_safe_float(snapshot.get("drawdown"), 0.0))
        var_95 = _pct_to_decimal(_safe_float(snapshot.get("var_95"), 0.0))
        corr_shift = abs(_safe_float(snapshot.get("corr_shift"), 0.0))
        volume_spike = _safe_float(snapshot.get("volume_spike_ratio"), 1.0)

        out: list[dict] = []

        if drawdown <= self.config.drawdown_threshold:
            out.append(
                Alert(
                    level="CRITICAL",
                    key="drawdown_critical",
                    title="Drawdown Critical",
                    message=f"drawdown {drawdown*100:.2f}% <= {self.config.drawdown_threshold*100:.2f}%",
                    recommendation="Reduce gross exposure and tighten risk budget.",
                    metadata={"drawdown": drawdown},
                    timestamp=_utc_now_iso(),
                ).to_dict()
            )

        if var_95 >= self.config.var_limit:
            out.append(
                Alert(
                    level="WARNING",
                    key="var_exceeded",
                    title="VaR Limit Exceeded",
                    message=f"VaR95 {var_95*100:.2f}% >= {self.config.var_limit*100:.2f}%",
                    recommendation="Scale down high-volatility positions.",
                    metadata={"var_95": var_95},
                    timestamp=_utc_now_iso(),
                ).to_dict()
            )

        if corr_shift >= self.config.corr_shift_threshold:
            out.append(
                Alert(
                    level="WARNING",
                    key="correlation_shift",
                    title="Correlation Shift Detected",
                    message=f"Correlation regime shift {corr_shift:.2f}",
                    recommendation="Re-check hedges and concentration.",
                    metadata={"corr_shift": corr_shift},
                    timestamp=_utc_now_iso(),
                ).to_dict()
            )

        if volume_spike >= self.config.volume_spike_threshold:
            out.append(
                Alert(
                    level="INFO",
                    key="volume_spike",
                    title="Volume Spike",
                    message=f"volume spike ratio {volume_spike:.2f}x",
                    recommendation="Watch for breakout and slippage risk.",
                    metadata={"volume_spike_ratio": volume_spike},
                    timestamp=_utc_now_iso(),
                ).to_dict()
            )

        return out

    def dispatch(
        self,
        alerts: list[dict],
        send_telegram_alert: bool = True,
        dashboard_sink: Optional[Callable[[dict], None]] = None,
    ) -> list[dict]:
        emitted: list[dict] = []

        for al in alerts:
            key = str(al.get("key") or "")
            if not key:
                continue
            if not self._should_emit(key):
                continue

            self._mark_emitted(key)
            emitted.append(al)

            if dashboard_sink is not None:
                try:
                    dashboard_sink(al)
                except Exception as exc:
                    log.warn("dashboard sink failed", error=exc)

            if send_telegram_alert:
                msg = (
                    f"[{al.get('level')}] {al.get('title')}\n"
                    f"{al.get('message')}\n"
                    f"Action: {al.get('recommendation')}"
                )
                send_telegram(msg, parse_mode="HTML")

        return emitted

    def process(
        self,
        snapshot: dict,
        send_telegram_alert: bool = True,
        dashboard_sink: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        candidates = self.evaluate(snapshot)
        emitted = self.dispatch(
            candidates,
            send_telegram_alert=send_telegram_alert,
            dashboard_sink=dashboard_sink,
        )
        return {
            "candidate_count": len(candidates),
            "emitted_count": len(emitted),
            "alerts": emitted,
            "timestamp": _utc_now_iso(),
        }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Intelligent alert manager")
    parser.add_argument("--drawdown", type=float, default=0.0, help="drawdown (-0.03 or -3)")
    parser.add_argument("--var95", type=float, default=0.0, help="VaR95 (0.02 or 2)")
    parser.add_argument("--corr-shift", type=float, default=0.0)
    parser.add_argument("--volume-spike", type=float, default=1.0)
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    out = AlertManager().process(
        {
            "drawdown": args.drawdown,
            "var_95": args.var95,
            "corr_shift": args.corr_shift,
            "volume_spike_ratio": args.volume_spike,
        },
        send_telegram_alert=not args.no_telegram,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
