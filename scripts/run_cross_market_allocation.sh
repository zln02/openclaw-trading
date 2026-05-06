#!/usr/bin/env bash
# Cross-market performance scoring → brain/portfolio/market_allocation.json
# 매일 07:00 crontab으로 실행

set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"
PYTHON_BIN="$WORKSPACE/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python runtime not found: $PYTHON_BIN" >&2
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] cross_market_manager 시작"

"$PYTHON_BIN" -m quant.portfolio.cross_market_manager "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] cross_market_manager 완료"
