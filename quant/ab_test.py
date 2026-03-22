"""Strategy A/B testing framework (v6 Phase 5).

Shadow mode: runs two strategies in parallel without executing trades.
Records hypothetical results for comparison after N days.

Usage:
    python -m quant.ab_test --market kr --days 30
"""
from __future__ import annotations

import argparse
import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config import BRAIN_PATH
from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import Priority, send_telegram

load_env()
log = get_logger("ab_test")

AB_TEST_DIR: Path = BRAIN_PATH / "ab_test"


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ShadowStrategy:
    """A strategy configuration used in shadow mode (no real execution)."""

    name: str
    market: str  # "kr", "us", "btc"
    params: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ShadowTrade:
    """A hypothetical trade recorded during shadow execution."""

    strategy_name: str
    symbol: str
    side: str  # "BUY" or "SELL"
    price: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    score: float = 0.0


# ── Pure helper functions ────────────────────────────────────────────────────

def calc_shadow_pnl(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate PnL from a list of shadow trades.

    Pairs BUY/SELL trades per symbol in order.  Unpaired trades are ignored.

    Returns:
        dict with total_pnl, trade_count, win_count, loss_count, win_rate.
    """
    # Group by symbol
    by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    for t in trades:
        by_symbol.setdefault(t["symbol"], []).append(t)

    total_pnl = 0.0
    win_count = 0
    loss_count = 0
    trade_count = 0

    for symbol, sym_trades in by_symbol.items():
        buys = [t for t in sym_trades if t["side"] == "BUY"]
        sells = [t for t in sym_trades if t["side"] == "SELL"]
        pairs = min(len(buys), len(sells))
        for i in range(pairs):
            pnl = sells[i]["price"] - buys[i]["price"]
            total_pnl += pnl
            trade_count += 1
            if pnl >= 0:
                win_count += 1
            else:
                loss_count += 1

    win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0.0
    return {
        "total_pnl": round(total_pnl, 4),
        "trade_count": trade_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
    }


def compare_strategies(
    a_trades: List[Dict[str, Any]],
    b_trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare two sets of shadow trades and determine a winner.

    Returns:
        dict with a_stats, b_stats, winner ("A", "B", or "TIE").
    """
    a_stats = calc_shadow_pnl(a_trades)
    b_stats = calc_shadow_pnl(b_trades)

    if a_stats["total_pnl"] > b_stats["total_pnl"]:
        winner = "A"
    elif b_stats["total_pnl"] > a_stats["total_pnl"]:
        winner = "B"
    else:
        winner = "TIE"

    return {"a_stats": a_stats, "b_stats": b_stats, "winner": winner}


# ── ABTest class ─────────────────────────────────────────────────────────────

class ABTest:
    """Manages a single A/B test between two shadow strategies."""

    def __init__(
        self,
        strategy_a: ShadowStrategy,
        strategy_b: ShadowStrategy,
        duration_days: int = 30,
    ) -> None:
        self.test_id: str = uuid.uuid4().hex[:12]
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.duration_days = duration_days
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.trades: List[Dict[str, Any]] = []

        AB_TEST_DIR.mkdir(parents=True, exist_ok=True)
        log.info(
            "AB test created: %s  A=%s vs B=%s  duration=%d days",
            self.test_id, strategy_a.name, strategy_b.name, duration_days,
        )

    # ── persistence ──────────────────────────────────────────────────────

    @property
    def _path(self) -> Path:
        return AB_TEST_DIR / f"{self.test_id}.json"

    def save(self) -> Path:
        """Persist current state to brain/ab_test/{test_id}.json."""
        data = {
            "test_id": self.test_id,
            "strategy_a": asdict(self.strategy_a),
            "strategy_b": asdict(self.strategy_b),
            "duration_days": self.duration_days,
            "created_at": self.created_at,
            "trades": self.trades,
        }
        AB_TEST_DIR.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        log.info("AB test saved: %s (%d trades)", self.test_id, len(self.trades))
        return self._path

    @classmethod
    def load(cls, test_id: str) -> "ABTest":
        """Load an existing AB test from disk."""
        path = AB_TEST_DIR / f"{test_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"AB test not found: {path}")
        data = json.loads(path.read_text())
        sa = ShadowStrategy(**data["strategy_a"])
        sb = ShadowStrategy(**data["strategy_b"])
        obj = cls.__new__(cls)
        obj.test_id = data["test_id"]
        obj.strategy_a = sa
        obj.strategy_b = sb
        obj.duration_days = data["duration_days"]
        obj.created_at = data["created_at"]
        obj.trades = data.get("trades", [])
        return obj

    # ── recording ────────────────────────────────────────────────────────

    def record_signal(
        self,
        strategy_name: str,
        symbol: str,
        side: str,
        price: float,
        score: float = 0.0,
    ) -> None:
        """Record a hypothetical trade signal from a shadow strategy.

        Args:
            strategy_name: Must match strategy_a.name or strategy_b.name.
            symbol: Ticker symbol (e.g. "005930", "AAPL", "BTC").
            side: "BUY" or "SELL".
            price: Current market price at signal time.
            score: Composite/confidence score that triggered the signal.
        """
        valid_names = {self.strategy_a.name, self.strategy_b.name}
        if strategy_name not in valid_names:
            log.warning(
                "Unknown strategy name '%s'; expected one of %s",
                strategy_name, valid_names,
            )
            return

        trade = ShadowTrade(
            strategy_name=strategy_name,
            symbol=symbol,
            side=side.upper(),
            price=price,
            score=score,
        )
        self.trades.append(asdict(trade))
        self.save()
        log.info(
            "[%s] %s %s @ %.4f (score=%.3f)",
            strategy_name, side.upper(), symbol, price, score,
        )

    # ── evaluation ───────────────────────────────────────────────────────

    def _trades_for(self, name: str) -> List[Dict[str, Any]]:
        return [t for t in self.trades if t["strategy_name"] == name]

    @staticmethod
    def _calc_sharpe(pnl_list: List[float]) -> float:
        """Annualized Sharpe ratio from a list of per-trade PnL values."""
        if len(pnl_list) < 2:
            return 0.0
        mean = sum(pnl_list) / len(pnl_list)
        var = sum((x - mean) ** 2 for x in pnl_list) / (len(pnl_list) - 1)
        std = math.sqrt(var) if var > 0 else 1e-9
        return round((mean / std) * math.sqrt(252), 4)

    @staticmethod
    def _calc_mdd(pnl_list: List[float]) -> float:
        """Maximum drawdown from cumulative PnL series."""
        if not pnl_list:
            return 0.0
        cumulative = 0.0
        peak = 0.0
        mdd = 0.0
        for pnl in pnl_list:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > mdd:
                mdd = dd
        return round(mdd, 4)

    @staticmethod
    def _calc_profit_factor(pnl_list: List[float]) -> float:
        """Profit factor = gross_profit / gross_loss."""
        gross_profit = sum(p for p in pnl_list if p > 0)
        gross_loss = abs(sum(p for p in pnl_list if p < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return round(gross_profit / gross_loss, 4)

    def _strategy_metrics(self, name: str) -> Dict[str, Any]:
        """Compute profit_factor, sharpe, mdd for one strategy."""
        trades = self._trades_for(name)
        by_symbol: Dict[str, List[Dict[str, Any]]] = {}
        for t in trades:
            by_symbol.setdefault(t["symbol"], []).append(t)

        pnl_list: List[float] = []
        for symbol, sym_trades in by_symbol.items():
            buys = [t for t in sym_trades if t["side"] == "BUY"]
            sells = [t for t in sym_trades if t["side"] == "SELL"]
            for i in range(min(len(buys), len(sells))):
                pnl_list.append(sells[i]["price"] - buys[i]["price"])

        return {
            "profit_factor": self._calc_profit_factor(pnl_list),
            "sharpe": self._calc_sharpe(pnl_list),
            "mdd": self._calc_mdd(pnl_list),
            "total_pnl": round(sum(pnl_list), 4),
            "trade_count": len(pnl_list),
        }

    def evaluate(self) -> Dict[str, Any]:
        """Evaluate both strategies and determine the winner.

        Returns:
            dict with keys: strategy_a, strategy_b (each with metrics),
            winner ("A", "B", or "TIE"), and test_id.
        """
        a_metrics = self._strategy_metrics(self.strategy_a.name)
        b_metrics = self._strategy_metrics(self.strategy_b.name)

        if a_metrics["total_pnl"] > b_metrics["total_pnl"]:
            winner = "A"
        elif b_metrics["total_pnl"] > a_metrics["total_pnl"]:
            winner = "B"
        else:
            winner = "TIE"

        result = {
            "test_id": self.test_id,
            "strategy_a": {
                "name": self.strategy_a.name,
                **a_metrics,
            },
            "strategy_b": {
                "name": self.strategy_b.name,
                **b_metrics,
            },
            "winner": winner,
        }
        log.info("AB evaluation: winner=%s  A_pnl=%.4f  B_pnl=%.4f",
                 winner, a_metrics["total_pnl"], b_metrics["total_pnl"])
        return result

    def is_complete(self) -> bool:
        """Check whether the test duration has elapsed."""
        start = datetime.fromisoformat(self.created_at)
        deadline = start + timedelta(days=self.duration_days)
        return datetime.now(timezone.utc) >= deadline


# ── CLI ──────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Strategy A/B testing (shadow mode)")
    parser.add_argument("--market", default="kr", choices=["kr", "us", "btc"],
                        help="Market to run the shadow test on")
    parser.add_argument("--days", type=int, default=30,
                        help="Duration of the A/B test in days")
    parser.add_argument("--evaluate", type=str, default=None,
                        help="Evaluate an existing test by ID")
    parser.add_argument("--list", action="store_true",
                        help="List all existing A/B tests")
    args = parser.parse_args()

    if args.list:
        AB_TEST_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(AB_TEST_DIR.glob("*.json"))
        if not files:
            log.info("No A/B tests found.")
            return
        for f in files:
            try:
                data = json.loads(f.read_text())
                a_name = data["strategy_a"]["name"]
                b_name = data["strategy_b"]["name"]
                n_trades = len(data.get("trades", []))
                log.info("  %s  %s vs %s  trades=%d  created=%s",
                         data["test_id"], a_name, b_name, n_trades,
                         data["created_at"][:10])
            except Exception:
                log.warning("  Could not read %s", f.name)
        return

    if args.evaluate:
        try:
            test = ABTest.load(args.evaluate)
        except FileNotFoundError as exc:
            log.error(str(exc))
            return
        result = test.evaluate()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        try:
            msg = (
                f"[AB Test] {test.test_id}\n"
                f"A ({result['strategy_a']['name']}): "
                f"PnL={result['strategy_a']['total_pnl']:.4f} "
                f"Sharpe={result['strategy_a']['sharpe']:.2f}\n"
                f"B ({result['strategy_b']['name']}): "
                f"PnL={result['strategy_b']['total_pnl']:.4f} "
                f"Sharpe={result['strategy_b']['sharpe']:.2f}\n"
                f"Winner: {result['winner']}"
            )
            send_telegram(msg, priority=Priority.INFO)
        except Exception:
            log.warning("Telegram send failed (non-critical)")
        return

    # Default: create a new demo test
    sa = ShadowStrategy(name=f"{args.market}_baseline", market=args.market)
    sb = ShadowStrategy(name=f"{args.market}_candidate", market=args.market)
    test = ABTest(sa, sb, duration_days=args.days)
    test.save()
    log.info(
        "Created A/B test %s for market=%s, duration=%d days. "
        "Use record_signal() to log shadow trades.",
        test.test_id, args.market, args.days,
    )
    print(f"Test ID: {test.test_id}")
    print(f"Saved to: {test._path}")


if __name__ == "__main__":
    _cli()
