#!/bin/bash
# Cron용 래퍼 — .env + openclaw.json 로드 후 btc/btc_trading_agent.py 실행 (실거래)
set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

PYTHON_BIN="$WORKSPACE/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python runtime not found: $PYTHON_BIN" >&2
  exit 1
fi

cd "$WORKSPACE"

echo "[CRON] $(date -Iseconds) ARGS=$@"
exec "$PYTHON_BIN" btc/btc_trading_agent.py "$@"
