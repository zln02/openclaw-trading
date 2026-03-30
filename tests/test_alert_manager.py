from __future__ import annotations

from pathlib import Path

from agents.alert_manager import AlertConfig, AlertManager


def test_check_alerts_normal_snapshot_yields_no_alerts(tmp_path: Path) -> None:
    manager = AlertManager(config=AlertConfig(cooldown_seconds=0))

    alerts = manager.evaluate(
        {
            "drawdown": -0.01,
            "var_95": 0.01,
            "corr_shift": 0.05,
            "volume_spike_ratio": 1.0,
        }
    )

    assert alerts == [], "normal portfolio snapshot should not emit any alerts"


def test_check_alerts_daily_loss_limit_exceeded_emits_alerts() -> None:
    manager = AlertManager(config=AlertConfig(cooldown_seconds=0))

    alerts = manager.evaluate(
        {
            "drawdown": -0.05,
            "var_95": 0.01,
            "corr_shift": 0.05,
            "volume_spike_ratio": 1.0,
        }
    )

    assert len(alerts) >= 1, "daily loss limit breach should emit at least one alert"


def test_check_alerts_drawdown_contains_drawdown_text() -> None:
    manager = AlertManager(config=AlertConfig(cooldown_seconds=0))

    alerts = manager.evaluate(
        {
            "drawdown": -0.06,
            "var_95": 0.01,
            "corr_shift": 0.05,
            "volume_spike_ratio": 1.0,
        }
    )

    assert any("drawdown" in (alert.get("message", "") + alert.get("title", "")).lower() for alert in alerts), "drawdown alerts should mention drawdown"


def test_send_alert_dispatches_to_telegram(mock_telegram, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.alert_manager._COOLDOWN_DIR", tmp_path)
    monkeypatch.setattr("agents.alert_manager.send_telegram", mock_telegram)
    manager = AlertManager(config=AlertConfig(cooldown_seconds=0))

    emitted = manager.dispatch(
        [
            {
                "level": "CRITICAL",
                "key": "drawdown_critical",
                "title": "Drawdown Critical",
                "message": "drawdown -5%",
                "recommendation": "Reduce exposure.",
            }
        ],
        send_telegram_alert=True,
    )

    assert len(emitted) == 1, "dispatch should emit the provided alert"
    assert mock_telegram.called, "dispatch should send a Telegram alert when enabled"
