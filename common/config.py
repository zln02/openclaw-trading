"""Shared paths and constants for the OpenClaw trading system."""
from pathlib import Path

OPENCLAW_ROOT = Path("/home/wlsdud5035/.openclaw")
WORKSPACE = OPENCLAW_ROOT / "workspace"
LOG_DIR = OPENCLAW_ROOT / "logs"

BRAIN_PATH = WORKSPACE / "brain"
MEMORY_PATH = WORKSPACE / "memory"

BTC_LOG = LOG_DIR / "btc_trading.log"
STOCK_TRADING_LOG = LOG_DIR / "stock_trading.log"
STOCK_CHECK_LOG = LOG_DIR / "stock_check.log"
STOCK_PREMARKET_LOG = LOG_DIR / "stock_premarket.log"
STOCK_COLLECTOR_LOG = LOG_DIR / "stock_collector.log"
US_TRADING_LOG = LOG_DIR / "us_trading.log"
DASHBOARD_LOG = LOG_DIR / "dashboard.log"

STRATEGY_JSON = WORKSPACE / "stocks" / "today_strategy.json"
OPENCLAW_JSON = OPENCLAW_ROOT / "openclaw.json"

DASHBOARD_PORT = 8080
