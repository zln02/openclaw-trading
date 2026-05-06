"""Tests for param_optimizer 백테스트 게이트 + decision_log + telegram summary."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from quant.param_optimizer import (_GATE_MDD_MARGIN, _GATE_MIN_TRADES,
                                   _GATE_SHARPE_MARGIN, ParamOptimizer,
                                   _apply_best_params, _backtest_gate,
                                   _log_decision)

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _engine_mock(sharpe: float, mdd_pct: float, n_trades: int = 10):
    """BacktestEngine 인스턴스 mock — .run(save=False) 결과 dict 주입."""
    instance = MagicMock()
    instance.run.return_value = {
        "ok": True,
        "metrics": {
            "sharpe": sharpe,
            "mdd_pct": mdd_pct,
            "n_trades": n_trades,
            "win_rate": 50.0,
            "total_return_pct": 5.0,
        },
    }
    return instance


def _patch_backtest_engine(baseline_metrics, new_metrics):
    """BacktestEngine 클래스 patch — 호출 순서: baseline 먼저, new 나중."""
    cls = MagicMock()
    cls.side_effect = [
        _engine_mock(**baseline_metrics),
        _engine_mock(**new_metrics),
    ]
    return patch("backtest.backtest_engine.BacktestEngine", cls)


# ── 단위 테스트: _backtest_gate ────────────────────────────────────────────────

class TestBacktestGate:
    def test_gate_pass_higher_sharpe_lower_mdd(self):
        """sharpe 향상 + MDD 개선 → 게이트 통과."""
        with _patch_backtest_engine(
            baseline_metrics={"sharpe": 1.0, "mdd_pct": -10.0},
            new_metrics={"sharpe": 1.5, "mdd_pct": -7.0},
        ):
            r = _backtest_gate({"rsi_window": 21}, {"rsi_window": 14})
        assert r["passed"] is True
        assert r["skipped"] is False

    def test_gate_fail_sharpe_below_098_margin(self):
        """new_sharpe=0.97 < baseline×0.98=0.98 → sharpe 회귀로 게이트 실패."""
        with _patch_backtest_engine(
            baseline_metrics={"sharpe": 1.0, "mdd_pct": -10.0},
            new_metrics={"sharpe": 0.97, "mdd_pct": -9.0},
        ):
            r = _backtest_gate({"rsi_window": 21}, {"rsi_window": 14})
        assert r["passed"] is False
        assert "sharpe" in r["reason"].lower() or "Sharpe" in r["reason"]

    def test_gate_fail_mdd_above_13_margin(self):
        """new_mdd=-14 → |14| > |10|×1.3=13 → MDD 악화로 게이트 실패."""
        with _patch_backtest_engine(
            baseline_metrics={"sharpe": 1.0, "mdd_pct": -10.0},
            new_metrics={"sharpe": 1.1, "mdd_pct": -14.0},
        ):
            r = _backtest_gate({"rsi_window": 21}, {"rsi_window": 14})
        assert r["passed"] is False
        assert "MDD" in r["reason"]

    def test_gate_skip_when_n_trades_below_3(self):
        """new n_trades=2 < _GATE_MIN_TRADES=3 → skipped=True, passed=True, reason '거래 부족'."""
        with _patch_backtest_engine(
            baseline_metrics={"sharpe": 1.0, "mdd_pct": -10.0, "n_trades": 10},
            new_metrics={"sharpe": 1.2, "mdd_pct": -8.0, "n_trades": 2},
        ):
            r = _backtest_gate({"rsi_window": 21}, {"rsi_window": 14})
        assert r["passed"] is True
        assert r["skipped"] is True
        assert "거래 부족" in r["reason"]


# ── 통합 테스트: _apply_best_params ───────────────────────────────────────────

def _best_params_json(params: dict, improved: bool = True) -> str:
    return json.dumps({"improved": improved, "params": params}, ensure_ascii=False)


def _agent_params_json(params: dict) -> str:
    return json.dumps(params, ensure_ascii=False)


class TestApplyBestParams:
    def test_gate_pass_calls_save_agent_params(self, tmp_path):
        """게이트 통과 시 _save_agent_params 1회 호출."""
        best_path = tmp_path / "best_params.json"
        best_path.write_text(_best_params_json({"rsi_window": 21}), encoding="utf-8")
        agent_path = tmp_path / "agent_params.json"
        agent_path.write_text(_agent_params_json({"rsi_window": 14}), encoding="utf-8")

        log_path = tmp_path / "decision_log.jsonl"

        with (
            patch("quant.param_optimizer._BEST_PARAMS_PATH", best_path),
            patch("quant.param_optimizer._AGENT_PARAMS_PATH", agent_path),
            patch("quant.param_optimizer._DECISION_LOG_PATH", log_path),
            _patch_backtest_engine(
                baseline_metrics={"sharpe": 1.0, "mdd_pct": -10.0},
                new_metrics={"sharpe": 1.5, "mdd_pct": -7.0},
            ),
            patch("quant.param_optimizer._save_agent_params") as mock_save,
        ):
            result = _apply_best_params(dry_run=False)

        assert result is not None
        assert result["applied"] is True
        mock_save.assert_called_once()

    def test_gate_fail_skips_save_agent_params(self, tmp_path):
        """게이트 실패 시 _save_agent_params 호출 0회."""
        best_path = tmp_path / "best_params.json"
        best_path.write_text(_best_params_json({"rsi_window": 21}), encoding="utf-8")
        agent_path = tmp_path / "agent_params.json"
        agent_path.write_text(_agent_params_json({"rsi_window": 14}), encoding="utf-8")

        log_path = tmp_path / "decision_log.jsonl"

        with (
            patch("quant.param_optimizer._BEST_PARAMS_PATH", best_path),
            patch("quant.param_optimizer._AGENT_PARAMS_PATH", agent_path),
            patch("quant.param_optimizer._DECISION_LOG_PATH", log_path),
            _patch_backtest_engine(
                baseline_metrics={"sharpe": 1.0, "mdd_pct": -10.0},
                # sharpe 0.97 → 게이트 실패
                new_metrics={"sharpe": 0.97, "mdd_pct": -9.0},
            ),
            patch("quant.param_optimizer._save_agent_params") as mock_save,
        ):
            result = _apply_best_params(dry_run=False)

        assert result is not None
        assert result["applied"] is False
        mock_save.assert_not_called()

    def test_gate_dry_run_never_saves(self, tmp_path):
        """dry_run=True 이면 게이트 통과여도 _save_agent_params 호출 0회."""
        best_path = tmp_path / "best_params.json"
        best_path.write_text(_best_params_json({"rsi_window": 21}), encoding="utf-8")
        agent_path = tmp_path / "agent_params.json"
        agent_path.write_text(_agent_params_json({"rsi_window": 14}), encoding="utf-8")

        log_path = tmp_path / "decision_log.jsonl"

        with (
            patch("quant.param_optimizer._BEST_PARAMS_PATH", best_path),
            patch("quant.param_optimizer._AGENT_PARAMS_PATH", agent_path),
            patch("quant.param_optimizer._DECISION_LOG_PATH", log_path),
            _patch_backtest_engine(
                baseline_metrics={"sharpe": 1.0, "mdd_pct": -10.0},
                new_metrics={"sharpe": 1.5, "mdd_pct": -7.0},
            ),
            patch("quant.param_optimizer._save_agent_params") as mock_save,
        ):
            result = _apply_best_params(dry_run=True)

        assert result is not None
        assert result["applied"] is False  # dry_run → applied=False
        mock_save.assert_not_called()


# ── decision_log.jsonl append ─────────────────────────────────────────────────

def test_decision_log_append_pass_and_fail(monkeypatch, tmp_path):
    """PASS + FAIL 두 케이스 연속 _log_decision → jsonl 2줄, decision 필드 검증."""
    log_path = tmp_path / "decision_log.jsonl"
    monkeypatch.setattr("quant.param_optimizer._DECISION_LOG_PATH", log_path)

    _log_decision({"decision": "APPLIED", "metrics": {"sharpe": 1.5}})
    _log_decision({"decision": "REJECTED", "metrics": {"sharpe": 0.7}})

    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["decision"] == "APPLIED"
    assert json.loads(lines[1])["decision"] == "REJECTED"


# ── 텔레그램 메시지 포맷 ───────────────────────────────────────────────────────

class TestTelegramMessageFormat:
    def _make_optimizer(self):
        return ParamOptimizer(supabase_client=MagicMock())

    def test_telegram_message_format_pass_fail_skip(self):
        """skip/pass/fail 3 분기별 ⏭/✅/❌ 포함 검증."""
        opt = self._make_optimizer()
        common_kwargs = dict(
            disabled_signals=[],
            param_changes={"rsi_window": {"old": 14, "new": 21}},
            perf_changes={},
            stats={},
            attribution_result={},
            dry_run=False,
        )

        # 1) skipped → ⏭
        with patch("quant.param_optimizer.send_telegram") as mock_tg:
            opt._send_summary(
                **common_kwargs,
                gate={
                    "passed": True,
                    "skipped": True,
                    "reason": "거래 부족",
                    "baseline_sharpe": 1.0,
                    "new_sharpe": 1.2,
                    "baseline_mdd": -10.0,
                    "new_mdd": -8.0,
                },
                applied=False,
            )
        msg_skip = mock_tg.call_args[0][0]
        assert "⏭" in msg_skip

        # 2) passed → ✅
        with patch("quant.param_optimizer.send_telegram") as mock_tg:
            opt._send_summary(
                **common_kwargs,
                gate={
                    "passed": True,
                    "skipped": False,
                    "reason": "",
                    "baseline_sharpe": 1.0,
                    "new_sharpe": 1.5,
                    "baseline_mdd": -10.0,
                    "new_mdd": -7.0,
                },
                applied=True,
            )
        msg_pass = mock_tg.call_args[0][0]
        assert "✅" in msg_pass

        # 3) failed → ❌
        with patch("quant.param_optimizer.send_telegram") as mock_tg:
            opt._send_summary(
                **common_kwargs,
                gate={
                    "passed": False,
                    "skipped": False,
                    "reason": "Sharpe 회귀",
                    "baseline_sharpe": 1.0,
                    "new_sharpe": 0.97,
                    "baseline_mdd": -10.0,
                    "new_mdd": -9.0,
                },
                applied=False,
            )
        msg_fail = mock_tg.call_args[0][0]
        assert "❌" in msg_fail
