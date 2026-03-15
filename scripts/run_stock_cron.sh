#!/bin/bash
# Cron용 KR 주식 래퍼.
# - .env + openclaw.json 로드
# - trading(default), check, status, premarket 지원

set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

PYTHON_BIN="$WORKSPACE/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python runtime not found: $PYTHON_BIN" >&2
  exit 1
fi

MODE="${1:-trading}"
TARGET="stocks/stock_trading_agent.py"

if [ "$MODE" = "premarket" ]; then
  shift
  TARGET="stocks/stock_premarket.py"
fi

cd "$WORKSPACE"

echo "[CRON][KR] $(date -Iseconds) MODE=$MODE ARGS=$*"
exec "$PYTHON_BIN" "$TARGET" "$@"
