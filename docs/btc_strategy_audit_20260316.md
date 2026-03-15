# BTC Strategy Audit

Date: 2026-03-16

## Verdict

The BTC stack is now materially safer than the previous revision, but it is not yet institutional-grade.
The current state is best described as a hardened production-oriented retail quant system.

## Confirmed Strengths

- Composite entry logic uses regime-aware thresholds, kimchi premium gating, funding crowding filters, and whale/news context.
- Circuit breaker checks are wired into live buy execution.
- All live sell paths now share explicit order validation and exception handling.
- Process-local buy locking reduces duplicate buys caused by delayed position writes.
- UTC-based timestamps and daily counters reduce drift between application time and Supabase time.
- Existing BTC regression tests pass locally via `python3 -m unittest tests.test_phase14_btc_top_tier`.

## Remaining Gaps

- Buy locking is still process-local, not distributed; multiple workers can still race without a DB or broker-side idempotency key.
- Position sizing is rule-based split buying, not portfolio-optimization or volatility-targeting.
- Partial take-profit state is stored as flags, but remaining quantity is not reconciled into a dedicated position ledger.
- Execution quality is still market-order centric; there is no explicit slippage budget, fill reconciliation, or venue failover.
- Research-loop weights can influence live scoring, but there is no hard promotion gate tied to live shadow performance.

## Near-Term Upgrade Targets

1. Add distributed idempotency for buy orders using a DB lock or unique order token.
2. Track remaining position quantity and realized PnL per partial exit in the BTC position table.
3. Add slippage/fill quality checks before and after live execution.
4. Require shadow-mode or walk-forward promotion checks before auto-applying research-loop parameters.
