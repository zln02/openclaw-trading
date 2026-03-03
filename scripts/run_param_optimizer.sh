#!/usr/bin/env bash
# Param Optimizer wrapper — 자율 파라미터 반영
# 매주 일요일 23:30 crontab으로 실행 (signal_evaluator 완료 후)

set -euo pipefail

WORKSPACE=/home/wlsdud5035/.openclaw/workspace

cd "$WORKSPACE"
source .venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M:%S')] param_optimizer 시작"

python -m quant.param_optimizer \
    --lookback "${PARAM_OPT_LOOKBACK:-7}" \
    "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] param_optimizer 완료"
