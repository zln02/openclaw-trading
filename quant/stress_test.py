"""Portfolio stress testing (v6 Phase 5).

Simulates portfolio impact under historical crisis scenarios:
- COVID 2020: -35% equities, -50% BTC
- Crypto Winter 2022: -75% BTC, -15% equities
- 2008 GFC: -55% equities, no BTC data
- Flash Crash: -10% all assets in 1 day

Usage:
    python -m quant.stress_test [--alert-threshold 15]
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from common.env_loader import load_env
from common.logger import get_logger
from common.telegram import Priority, send_telegram

load_env()
log = get_logger("stress_test")


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class StressScenario:
    """A single crisis scenario definition.

    Attributes:
        name: Short identifier (e.g. "COVID_2020").
        description: Human-readable description of the scenario.
        asset_shocks: Mapping of asset class to percentage loss (positive number).
            Keys should match portfolio_weights keys (e.g. "btc", "kr_equity", "us_equity").
    """
    name: str
    description: str
    asset_shocks: Dict[str, float] = field(default_factory=dict)


# ── Pre-defined scenarios ────────────────────────────────────────────────────

COVID_2020 = StressScenario(
    name="COVID_2020",
    description="COVID-19 pandemic crash (Mar 2020): equities -35%, BTC -50%",
    asset_shocks={
        "btc": 50.0,
        "kr_equity": 35.0,
        "us_equity": 35.0,
    },
)

CRYPTO_WINTER_2022 = StressScenario(
    name="CRYPTO_WINTER_2022",
    description="Crypto winter (2022): BTC -75%, equities -15%",
    asset_shocks={
        "btc": 75.0,
        "kr_equity": 15.0,
        "us_equity": 15.0,
    },
)

GFC_2008 = StressScenario(
    name="GFC_2008",
    description="Global Financial Crisis (2008): equities -55%, no BTC data",
    asset_shocks={
        "kr_equity": 55.0,
        "us_equity": 55.0,
    },
)

FLASH_CRASH = StressScenario(
    name="FLASH_CRASH",
    description="Flash crash: all assets -10% in a single day",
    asset_shocks={
        "btc": 10.0,
        "kr_equity": 10.0,
        "us_equity": 10.0,
    },
)

ALL_SCENARIOS: List[StressScenario] = [
    COVID_2020,
    CRYPTO_WINTER_2022,
    GFC_2008,
    FLASH_CRASH,
]


# ── Stress test engine ───────────────────────────────────────────────────────

class StressTest:
    """Run stress scenarios against a portfolio.

    Args:
        portfolio_weights: Mapping of asset class -> weight (0-1). Must sum to ~1.0.
            Example: {"btc": 0.3, "kr_equity": 0.3, "us_equity": 0.4}
        portfolio_value: Total portfolio value in base currency (KRW).
    """

    def __init__(
        self,
        portfolio_weights: Dict[str, float],
        portfolio_value: float,
    ) -> None:
        self.portfolio_weights = portfolio_weights
        self.portfolio_value = portfolio_value

    def run_scenario(self, scenario: StressScenario) -> Dict:
        """Simulate a single stress scenario.

        Returns:
            Dict with keys:
                scenario_name: str
                description: str
                portfolio_loss_pct: float — total portfolio loss percentage
                portfolio_loss_value: float — absolute loss amount
                per_asset: dict[str, dict] — per-asset breakdown
        """
        per_asset: Dict[str, Dict] = {}
        total_loss_pct = 0.0

        for asset, weight in self.portfolio_weights.items():
            shock_pct = scenario.asset_shocks.get(asset, 0.0)
            asset_loss_pct = weight * shock_pct
            asset_loss_value = self.portfolio_value * (asset_loss_pct / 100.0)

            per_asset[asset] = {
                "weight": weight,
                "shock_pct": shock_pct,
                "loss_pct": round(asset_loss_pct, 4),
                "loss_value": round(asset_loss_value, 2),
            }
            total_loss_pct += asset_loss_pct

        return {
            "scenario_name": scenario.name,
            "description": scenario.description,
            "portfolio_loss_pct": round(total_loss_pct, 4),
            "portfolio_loss_value": round(
                self.portfolio_value * (total_loss_pct / 100.0), 2
            ),
            "per_asset": per_asset,
        }

    def run_all_scenarios(
        self,
        scenarios: Optional[List[StressScenario]] = None,
    ) -> List[Dict]:
        """Run all predefined scenarios (or a custom list).

        Returns:
            List of result dicts from run_scenario().
        """
        targets = scenarios or ALL_SCENARIOS
        results = []
        for sc in targets:
            result = self.run_scenario(sc)
            log.info(
                "Scenario %s: portfolio loss %.2f%%",
                sc.name,
                result["portfolio_loss_pct"],
            )
            results.append(result)
        return results

    def check_alerts(
        self,
        threshold_pct: float = 15.0,
        scenarios: Optional[List[StressScenario]] = None,
    ) -> List[Dict]:
        """Return scenarios where portfolio loss exceeds threshold.

        Args:
            threshold_pct: Alert if portfolio loss >= this percentage.
            scenarios: Optional list of scenarios (defaults to ALL_SCENARIOS).

        Returns:
            List of result dicts that exceed the threshold.
        """
        results = self.run_all_scenarios(scenarios)
        alerts = [
            r for r in results
            if r["portfolio_loss_pct"] >= threshold_pct
        ]
        if alerts:
            log.warning(
                "%d scenario(s) exceed %.1f%% loss threshold",
                len(alerts),
                threshold_pct,
            )
        else:
            log.info(
                "All scenarios within %.1f%% threshold", threshold_pct
            )
        return alerts


# ── Telegram report ──────────────────────────────────────────────────────────

def send_stress_report(
    results: List[Dict],
    threshold_pct: float = 15.0,
) -> None:
    """Send a Telegram alert if any scenario exceeds the loss threshold.

    Args:
        results: List of result dicts from StressTest.run_all_scenarios().
        threshold_pct: Only alert if at least one scenario >= this.
    """
    alerts = [r for r in results if r["portfolio_loss_pct"] >= threshold_pct]

    if not alerts:
        log.info("Stress report: no scenarios exceed %.1f%% — skipping Telegram", threshold_pct)
        return

    lines = [f"[Stress Test] {len(alerts)} scenario(s) exceed {threshold_pct:.0f}% loss\n"]
    for r in alerts:
        lines.append(
            f"  {r['scenario_name']}: -{r['portfolio_loss_pct']:.1f}% "
            f"({r['portfolio_loss_value']:,.0f} KRW)"
        )
        for asset, info in r["per_asset"].items():
            if info["shock_pct"] > 0:
                lines.append(
                    f"    {asset}: shock -{info['shock_pct']:.0f}%, "
                    f"loss -{info['loss_pct']:.1f}%"
                )

    msg = "\n".join(lines)
    log.warning("Sending stress test alert:\n%s", msg)

    try:
        send_telegram(msg, priority=Priority.IMPORTANT)
    except Exception as exc:
        log.error("Failed to send stress report via Telegram: %s", exc)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio stress test")
    parser.add_argument(
        "--alert-threshold",
        type=float,
        default=15.0,
        help="Alert if any scenario loss >= this %% (default: 15)",
    )
    args = parser.parse_args()

    # Default portfolio weights — adjust to match actual allocation
    portfolio_weights: Dict[str, float] = {
        "btc": 0.30,
        "kr_equity": 0.30,
        "us_equity": 0.40,
    }
    # Approximate total portfolio value (KRW)
    portfolio_value = 10_000_000.0

    log.info(
        "Running stress test: value=%.0f KRW, threshold=%.1f%%",
        portfolio_value,
        args.alert_threshold,
    )

    tester = StressTest(portfolio_weights, portfolio_value)
    results = tester.run_all_scenarios()

    # Print summary to stdout
    print(f"\n{'='*60}")
    print(f"  Stress Test Results (threshold: {args.alert_threshold:.0f}%)")
    print(f"{'='*60}")
    for r in results:
        marker = " ** ALERT **" if r["portfolio_loss_pct"] >= args.alert_threshold else ""
        print(
            f"  {r['scenario_name']:<25s} "
            f"Loss: -{r['portfolio_loss_pct']:.1f}% "
            f"({r['portfolio_loss_value']:>12,.0f} KRW)"
            f"{marker}"
        )
    print(f"{'='*60}\n")

    send_stress_report(results, threshold_pct=args.alert_threshold)


if __name__ == "__main__":
    main()
