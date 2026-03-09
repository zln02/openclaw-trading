#!/usr/bin/env bash
# Signal IC/IR evaluator wrapper
# 매주 일요일 23:00 crontab으로 실행

set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"
source .venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M:%S')] signal_evaluator 시작"

python -m quant.signal_evaluator \
    --lookback "${SIGNAL_LOOKBACK:-90}" \
    --window "${SIGNAL_WINDOW:-14}" \
    "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] signal_evaluator 완료"
