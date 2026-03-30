# Changelog

All notable changes to OpenClaw Trading System.

## [v6.1] - 2026-03-30

### Added

- BTC regime classification with dynamic weight multipliers (BULL/BEAR/CRISIS)
- BTC ML ensemble: XGBoost + LightGBM + CatBoost + Stacking
- BTC ML live features: kimchi premium, Fear&Greed API, multi-timeframe (1h RSI, volatility)
- BTC SmartRouter integration for large orders (>=5M KRW, logging mode)
- Correlation monitor (cross-market concentration risk detection)
- CI/CD pipeline: lint (flake8/isort) -> test (pytest) -> security
- Unit tests: 39+ tests covering signals, risk guards, agents
- Telegram commands: /drawdown, /daily_loss, /resume confirmation flow
- Dashboard ErrorBoundary + chart error/empty state handling
- Prometheus node-exporter + agent metrics jobs
- self_healer: memory/Supabase checks, 5min cron
- agents/README.md, cron timing matrix documentation

### Changed

- Config centralization: API_RETRY_CONFIG, ML_BLEND_CONFIG, ROUTER_THRESHOLDS
- Error handling hardened: specific exceptions, exc_info logging
- print() -> log migration for 8 production files
- KST timezone for daily loss calculations (KR/BTC)
- PARAM_BOUNDS validation with clamping
- Supabase auto-reconnect (3 retries, 30s cooldown)
- Upbit 429 exponential backoff
- api.js fetchJSONSafe exponential backoff (2^attempt)
- Type hints added to 15 public functions

### Fixed

- stock_trading_agent 5 silent except blocks (logging added)
- btc_api.py RISK variable import
- test_phase14 mock target correction

## [v6.0] - 2026-03-18

### Added

- Supabase run_query_with_retry() auto-reconnect wrapper
- Dashboard v6.0 overhaul (React + Vite SPA)

## [v5.0] - 2026-03-09

### Added

- Phase 15: CI/CD, Docker, security audit
- Phase 14: AI 5-agent team, company module
- Phase 13: Signal IC/IR evaluator, news batch analysis

## [v4.0] - 2026-03-03

### Added

- Level 4->5 upgrade: alpha researcher, param optimizer, ML retrain loop
- Factor attribution (weekly PnL by factor)
- ML blending (rule 60% + ML 40%)

## [v3.0] - 2026-02-20

### Added

- KR/US stock agents
- Kiwoom client integration
- Telegram bot with /status, /stop, /sell_all
- DrawdownGuard, PositionSizer (Kelly)

## [v2.0] - 2026-02-10

### Added

- BTC trading agent (Upbit)
- FastAPI dashboard
- Regime classifier
- News analyst

## [v1.0] - 2026-01-15

### Added

- Initial release: BTC signal scoring, basic dashboard
