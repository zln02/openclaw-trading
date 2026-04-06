#!/usr/bin/env bash
# Param Optimizer wrapper — 자율 파라미터 반영
# 매주 일요일 23:30 crontab으로 실행 (signal_evaluator 완료 후)

set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"
source .venv/bin/activate
export PYTHONPATH="$WORKSPACE"  # audit fix: 모듈 경로 명시

echo "[$(date '+%Y-%m-%d %H:%M:%S')] param_optimizer 시작"

# signal_evaluator 완료 대기: weights.json이 최근 60분 이내에 갱신됐는지 확인
WEIGHTS_FILE="$WORKSPACE/brain/signal-ic/weights.json"
if [ -f "$WEIGHTS_FILE" ]; then
    WEIGHTS_AGE=$(( $(date +%s) - $(stat -c %Y "$WEIGHTS_FILE") ))
    if [ "$WEIGHTS_AGE" -gt 3600 ]; then
        echo "[WARN] weights.json 이 ${WEIGHTS_AGE}초 전 갱신 — signal_evaluator 미완료 가능성, 스킵"
        exit 0
    fi
else
    echo "[WARN] weights.json 없음 — signal_evaluator 미실행, 스킵"
    exit 0
fi

python -m quant.param_optimizer \
    --lookback "${PARAM_OPT_LOOKBACK:-7}" \
    "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] param_optimizer 완료"
