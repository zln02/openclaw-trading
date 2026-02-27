"""Phase 17 portfolio module tests."""
from __future__ import annotations

import unittest

from quant.portfolio.attribution import PerformanceAttribution, brinson_attribution
from quant.portfolio.optimizer import PortfolioOptimizer
from quant.portfolio.rebalancer import PortfolioRebalancer


class OptimizerTests(unittest.TestCase):
    def test_optimizer_returns_normalized_weights(self) -> None:
        optimizer = PortfolioOptimizer()
        out = optimizer.optimize(
            expected_returns={
                "BTC": 0.2,
                "A005930": 0.1,
                "A000660": 0.09,
                "AAPL": 0.11,
                "MSFT": 0.10,
                "NVDA": 0.14,
            },
            covariance={
                "BTC": {"BTC": 0.20},
                "A005930": {"A005930": 0.05},
                "A000660": {"A000660": 0.06},
                "AAPL": {"AAPL": 0.04},
                "MSFT": {"MSFT": 0.03},
                "NVDA": {"NVDA": 0.08},
            },
            asset_class_map={
                "BTC": "CRYPTO",
                "A005930": "KR",
                "A000660": "KR",
                "AAPL": "US",
                "MSFT": "US",
                "NVDA": "US",
            },
            method="mean_variance",
        )
        total = sum(out["weights"].values())
        self.assertAlmostEqual(total, 1.0, places=6)
        for w in out["weights"].values():
            self.assertGreaterEqual(w, 0.0)


class RebalancerTests(unittest.TestCase):
    def test_rebalance_trigger_and_orders(self) -> None:
        rebalancer = PortfolioRebalancer()
        out = rebalancer.build_rebalance_orders(
            current_weights={"BTC": 0.55, "AAPL": 0.45},
            target_weights={"BTC": 0.40, "AAPL": 0.60},
            portfolio_value=100000,
            prices={"BTC": 100000, "AAPL": 200},
            as_of="2026-02-27",
            last_rebalance_date="2026-01-20",
        )
        self.assertTrue(out["trigger"])
        self.assertGreater(len(out["orders"]), 0)
        self.assertGreaterEqual(out["summary"]["estimated_cost"], 0.0)


class AttributionTests(unittest.TestCase):
    def test_brinson_active_return_consistency(self) -> None:
        out = brinson_attribution(
            portfolio_weights={"US": 0.6, "KR": 0.4},
            benchmark_weights={"US": 0.5, "KR": 0.5},
            portfolio_returns={"US": 0.10, "KR": 0.04},
            benchmark_returns={"US": 0.08, "KR": 0.05},
        )
        rows_sum = sum(r["total_effect"] for r in out["rows"])
        self.assertAlmostEqual(rows_sum, out["active_return"], places=6)

    def test_factor_contribution(self) -> None:
        rep = PerformanceAttribution().factor_contribution(
            factor_exposure={"VALUE": 0.3, "MOMENTUM": 0.4, "QUALITY": 0.2},
            factor_return={"VALUE": 0.02, "MOMENTUM": -0.01, "QUALITY": 0.03},
        )
        self.assertIn("rows", rep)
        self.assertAlmostEqual(
            rep["total_factor_contribution"],
            0.3 * 0.02 + 0.4 * (-0.01) + 0.2 * 0.03,
            places=8,
        )


if __name__ == "__main__":
    unittest.main()
