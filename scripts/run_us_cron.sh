#!/bin/bash
# Cron wrapper for US stock agent.
# - Loads env from .env + openclaw.json
# - Supports: trading(default), check, status, premarket

set -u

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

PYTHON_BIN="$WORKSPACE/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python runtime not found: $PYTHON_BIN" >&2
  exit 1
fi

MODE="${1:-trading}"
TARGET="stocks/us_stock_trading_agent.py"

if [ "$MODE" = "premarket" ]; then
  shift
  TARGET="stocks/us_stock_premarket.py"
fi

cd "$WORKSPACE"

echo "[CRON][US] $(date -Iseconds) MODE=$MODE ARGS=$*"
exec "$PYTHON_BIN" "$TARGET" "$@"
