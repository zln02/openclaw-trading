#!/bin/bash
# Cron wrapper for US stock agent.
# - Loads env from .env + openclaw.json
# - Supports: trading(default), check, status, premarket

set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"

MODE="${1:-trading}"
TARGET="stocks/us_stock_trading_agent.py"

if [ "$MODE" = "premarket" ]; then
  shift
  TARGET="stocks/us_stock_premarket.py"
fi

echo "[CRON][US] $(date -Iseconds) MODE=$MODE ARGS=$*"
exec .venv/bin/python3 "$TARGET" "$@"
