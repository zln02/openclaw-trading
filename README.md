# OpenClaw Trading System

<p align="center"><strong>BTC · KR Stocks · US Stocks — Fully Automated Quantitative Trading Platform</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge" alt="Python 3.11+" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/BTC-Live%20Trading-orange?style=for-the-badge" alt="BTC Live Trading" />
  <img src="https://img.shields.io/badge/KR-Paper%20Trading-yellow?style=for-the-badge" alt="KR Paper Trading" />
  <img src="https://img.shields.io/badge/US-Dry--Run-lightgrey?style=for-the-badge" alt="US Dry-Run" />
  <img src="https://img.shields.io/badge/v6.0-Production-blueviolet?style=for-the-badge" alt="v6.0 Production" />
  <img src="https://img.shields.io/badge/Level%205-Research%20Loop-purple?style=for-the-badge" alt="Level 5 Research Loop" />
  <a href="https://github.com/zln02/openclaw-trading/stargazers"><img src="https://img.shields.io/github/stars/zln02/openclaw-trading?style=for-the-badge&logo=github&label=Stars" alt="GitHub Stars" /></a>
</p>

<p align="center">
  <a href="README.ko.md">한국어 README</a>
</p>

<p align="center">
  <img src="docs/images/dashboard-btc.png" alt="OpenClaw Dashboard — BTC page with sidebar, composite score, candlestick chart, and strategy panel" width="1200" />
</p>

---

## Overview

OpenClaw is a production-grade automated trading platform covering three markets simultaneously with a shared research loop and real-time dashboard.

| Market | Mode | Broker | Signal Engine |
|--------|------|--------|---------------|
| **BTC** | Live | Upbit | 10-factor composite score + regime filter |
| **KR Stocks** | Paper | Kiwoom | Rule-based 60% + XGBoost ML 40% blend |
| **US Stocks** | Dry-run | yfinance | Multi-factor momentum ranking + regime gate |

The system is self-improving: a weekly research loop evaluates signal IC/IR, auto-tunes parameters, and feeds improvements back into live agents.

---

## Quick Start

### Prerequisites

- Python 3.11+, Docker & Docker Compose
- Upbit API keys (BTC live trading)
- Telegram Bot Token (alerts & control)
- Optional: Kiwoom credentials (KR paper), Supabase project

```bash
git clone https://github.com/zln02/openclaw-trading
cd openclaw-trading
cp btc/.env.example .env              # Create a base env file
bash scripts/split_docker_env.sh .env # Generate .env.runtime + .docker-secrets/
docker compose up -d                  # Launch all services
```

The dashboard is available at `http://localhost:8080`. Docker Compose runs 5 services:
`dashboard`, `btc-agent`, `kr-agent`, `us-agent`, and `telegram-bot`.

---

## Features

<details>
<summary><strong>BTC — 10-Factor Composite Signal Engine</strong></summary>

The BTC agent runs a 10-factor composite scoring model (0–100 points) every cycle:

| Component | Max Score | Signal Logic |
|-----------|----------:|-------------|
| Fear & Greed | 22 | Contrarian — extreme fear = opportunity |
| RSI (daily) | 20 | Oversold reversal detection |
| Bollinger Band | 12 | Lower band proximity |
| HTF Trend | 12 | EMA-20/50 crossover direction |
| Volume (daily) | 10 | Conviction filter |
| Funding Rate | 8 | Short crowding = buy signal |
| News Sentiment | ±8 | Claude/GPT news analysis |
| Long/Short Ratio | 6 | Contrarian positioning |
| OI / Whale | 5 | On-chain flow confirmation |
| Regime Bonus | ±10 | BULL/TRANSITION/BEAR/CORRECTION overlay |

**Entry conditions:**
- Composite ≥ 50 (NORMAL regime), ≥ 60 (defensive), ≥ 65 (BEAR/CRISIS)
- F&G ≤ 15 extreme fear override (bypasses score threshold)
- Kimchi premium ≥ 5% → buy blocked
- Funding rate long-crowded → buy blocked
- Whale signal directly wired to composite

**Risk controls:**
- Stop-loss: −3% (ATR-based dynamic)
- Partial TP: +2% → 50%, +3% → 50% remaining, +4% → full exit
- Trailing stop: adaptive 1.5–2.5%
- Daily loss limit: −8% · Circuit breaker: WARNING −15% / HALT −25% / EMERGENCY −35%
- Thread-safe buy lock, 1-hour cooldown, max 2 trades/day

</details>

<details>
<summary><strong>KR Stocks — Rule + ML Blend</strong></summary>

- **Signal:** Rule-based score (60%) blended with XGBoost ML model (40%)
- **Universe:** 51-stock WATCHLIST + strategy picks merged; top 30 deep-analysed per cycle
- **ML:** Multi-horizon XGBoost (3d/5d/10d) + LightGBM + CatBoost stacking ensemble
- **Walk-forward validation:** TimeSeriesSplit CV with SHAP analysis
- **Regime-aware:** Momentum/quality factor weights adjusted per market regime (RISK_OFF etc.)
- **Investor trend:** Kiwoom institutional flow as primary signal, KRX as fallback
- **Risk:** −2.5% stop-loss, +8% take-profit, partial TP at +5%, 60-min cooldown

</details>

<details>
<summary><strong>US Stocks — Momentum Ranking</strong></summary>

- **Universe:** ~56 US equities screened for momentum, value, and quality
- **Signal:** Multi-factor score (RSI, relative strength, BB, volume, PE/PB, ROE)
- **Market filter:** S&P 500 regime (BULL/CORRECTION/BEAR) gates all buy decisions
- **ML drift gate:** PSI-based feature drift detection blocks trades when model is stale
- **Execution:** Market-hour aware, max 3 buys/day, 2-hour cooldown, DRY-RUN mode

</details>

<details>
<summary><strong>Level 5 Research Loop</strong></summary>

Weekly automated parameter refinement:

```
[Saturday 22:00]  alpha_researcher.py  → brain/alpha/best_params.json
[Sunday  23:00]   signal_evaluator.py  → IC/IR per signal → weights.json
[Sunday  23:30]   param_optimizer.py   → auto-apply params + Telegram report
[Daily   08:30]   ml_model.py retrain  → live trade feedback loop
```

- **Alpha Researcher:** Grid-search over rule parameters, ranks by IC/IR
- **Signal Evaluator:** Pearson IC, permutation-test significance, rolling IR
- **Param Optimizer:** Applies improvements only when IR improvement ≥ threshold
- **Attribution:** Weekly factor PnL attribution with auto-downweighting of weak factors

</details>

<details>
<summary><strong>AI Agent Team</strong></summary>

5 Claude-powered agents run in a shared decision loop:

| Agent | Model | Role |
|-------|-------|------|
| Orchestrator | Claude Opus 4.6 | Decision coordination, adaptive thinking |
| Market Analyst | Claude Sonnet 4.6 | Market regime + signal generation |
| News Analyst | Claude Haiku 4.5 | News sentiment, event detection |
| Risk Manager | Claude Sonnet 4.6 | Drawdown, VaR, position risk |
| Reporter | Claude Haiku 4.5 | Daily/weekly reports, Telegram delivery |

The decision layer combines market data, fear & greed, kimchi premium, portfolio state, and risk metrics before issuing BUY/SELL/HOLD actions.

</details>

<details>
<summary><strong>Dashboard (v6.0)</strong></summary>

React (Vite) + FastAPI dashboard at `http://localhost:8080`:

**Layout**
- Fixed 220px sidebar with live portfolio summary (BTC + KR + US → KRW total), health indicator, and relative-time refresh stamp
- Mobile: hamburger slide-in sidebar, auto-close on navigation
- Smooth page transitions via framer-motion

**BTC Page**
- Account banner: KRW balance, BTC evaluation, total assets, unrealized PnL, win rate
- Full candlestick chart with **6 timeframes** (5분 / 10분 / 1시간 / 주봉 / 월봉 / 연봉)
- Left rail: spot price, 6-signal progress bars, market filters (funding / L/S ratio / execution log)
- Right rail: composite score radial gauge, current position card, agent strategy panel

**KR Stocks Page**
- Account banner: deposit, equity evaluation, purchase cost, unrealized PnL, total assets
- Full-width price chart with **6 timeframes** (5분 / 1시간 / 1개월 / 3개월 / 6개월 / 1년)
- **Stock search** dropdown: searches by name or code across held positions + momentum ranking
- Portfolio pie chart + holdings table (avg entry, PnL amount, %, weight)
- Market summary cards, strategy panel, momentum ranking, trade history

**US Stocks Page**
- Account banner: invested/current USD, unrealized PnL ($ + ₩ FX-converted), position count
- Index cards: S&P 500, NASDAQ, DOW, USD/KRW with sparklines
- Full-width price chart with **6 timeframes** (5일 / 1개월 / 3개월 / 6개월 / 1년 / 5년)
- **Symbol search** dropdown across held positions + momentum ranking
- Momentum ranking table, open positions table, recent trade log, strategy panel

**Agents Page**
- 5-agent decision history with confidence scores and reasoning

All pages auto-refresh via polling (30–300s depending on data type); auth-protected with rate-limited login.

</details>

<details>
<summary><strong>Security</strong></summary>

- API keys stored in `.env` files, never committed (`.gitignore` enforced)
- Docker secrets mounted at `/run/local-secrets/` (or `/run/secrets/`)
- Dashboard auth: HTTP Basic, `secrets.compare_digest`, 5-attempt rate limiting (5 min lockout)
- CORS: env-configurable allowlist, `allow_credentials=False`, GET/OPTIONS only
- All API routes protected: `dependencies=[Depends(_require_auth)]` at router level
- `/health` endpoint intentionally unauthenticated (liveness probe only)
- `/assets/` static files served separately (no sensitive data, no auth required)
- Circuit breaker: 3-level portfolio drawdown guard (WARNING / HALT / EMERGENCY)
- `company/tools.py` bash: blocklist regex + `_safe_path()` workspace confinement
- `pre-commit` hooks: detect-private-key, flake8, isort

</details>

---

## Architecture

```mermaid
flowchart LR

subgraph Ext["📡 External APIs"]
  Upbit["Upbit\nBTC Live"]
  Kiwoom["Kiwoom\nKR Paper"]
  YF["yfinance\nUS Dry-Run"]
  Claude["Claude AI\nAgents"]
end

subgraph Core["🤖 Trading Engine"]
  BTC["BTC Agent\n10-factor composite"]
  KR["KR Agent\nRule 60% + ML 40%"]
  US["US Agent\nMomentum rank"]
  CB["Circuit Breaker\nWARNING/HALT/EMRG"]
end

subgraph Research["🔬 Level 5 Loop"]
  Alpha["Alpha Researcher\nSat 22:00"]
  Eval["Signal Evaluator\nSun 23:00"]
  Opt["Param Optimizer\nSun 23:30"]
end

subgraph Infra["🗄️ Infrastructure"]
  DB["Supabase\nPostgreSQL"]
  Docker["Docker Compose\n5 containers"]
end

Output["📊 Dashboard :8080\n📱 Telegram Bot\n🔔 Alerts"]

Ext --> Core
Core --> CB --> DB
DB --> Research --> Core
Docker --> Core
Core --> Output
```

---

## Project Structure

```text
.
├── agents/              # AI agent team (orchestrator, analysts, reporter)
├── btc/                 # BTC agent, routes (btc/kr/us APIs), signals, strategies
│   └── routes/          # btc_api.py · stock_api.py · us_api.py
├── common/              # Config, env loader, logger, Telegram, Supabase, circuit breaker
├── company/             # AI Software Company (CEO→specialist delegation, bash sandbox)
├── dashboard/           # React + Vite frontend
│   └── src/
│       ├── components/  # Layout (sidebar), StrategyPanel, UI primitives
│       ├── hooks/       # usePolling
│       ├── pages/       # BtcPage · KrStockPage · UsStockPage · AgentsPage
│       └── styles/      # tokens.css (design system)
├── docs/                # Documentation, audit reports, specs
│   └── images/          # dashboard-btc.png
├── execution/           # TWAP/VWAP execution, smart routing, slippage
├── quant/               # Alpha research, signal evaluator, param optimizer, risk, portfolio
├── scripts/             # Cron wrappers, health checks, agent loop runner
├── secretary/           # Autonomous helper, Notion integration, memory
├── stocks/              # KR/US agents, ML model, Kiwoom client, Telegram bot
├── tests/               # Pytest suite (metrics, utils, trade calculations)
├── docker-compose.yml   # 5-service runtime
├── Dockerfile
├── pytest.ini
├── README.md            # English README (this file)
└── README.ko.md         # Korean README
```

---

## Roadmap

- [x] Level 3: Adaptive Composite Signals
- [x] Level 4: Factor Model Operations (IC/IR → live weights)
- [x] Level 5: Research-to-Production Loop (alpha → signal eval → param opt)
- [x] Phase 14: AI Agent Team (5-agent Claude-powered decision loop)
- [x] Phase 15: CI/CD pipeline, Docker hardening, pre-commit hooks, security audit
- [x] v6.0: Dashboard overhaul — sidebar layout, timeframe selectors, stock/symbol search, strategy panels, account banners
- [x] Safety hardening: buy lock, order validation, UTC alignment, circuit breaker, drawdown guard
- [x] Security hardening: defusedxml RSS parsing, joblib model serialization, bash sandbox blocklist
- [ ] Level 6: Multi-Strategy Portfolio (Long-Short + Market Neutral)
- [ ] ML dead feature cleanup (13 inactive features → AUC target >0.70)
- [ ] KR partial TP quantity tracking fix
- [ ] Dashboard: async-safe blocking API calls, React Context shared portfolio state
- [ ] Portfolio Analytics page (Sharpe, Sortino, MDD chart, rolling returns)
- [ ] Level 7: On-chain DEX Arbitrage
- [ ] Multi-Exchange Support (Binance, Bybit)
- [ ] Mobile Dashboard (React Native / PWA)

---

## Contributing

Open an issue or PR if you want to contribute improvements.

## License

MIT License — see [LICENSE](LICENSE).
