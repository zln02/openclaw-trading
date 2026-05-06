#!/usr/bin/env bash
# Param Optimizer wrapper — 자율 파라미터 반영
# 매주 일요일 23:30 crontab으로 실행 (signal_evaluator 완료 후)

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

echo "[$(date '+%Y-%m-%d %H:%M:%S')] param_optimizer 시작"

"$PYTHON_BIN" -m quant.param_optimizer \
    --lookback "${PARAM_OPT_LOOKBACK:-7}" \
    "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] param_optimizer 완료"
