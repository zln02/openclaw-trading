#!/usr/bin/env bash
# Alpha Researcher wrapper — 룰 기반 파라미터 그리드서치
# 매주 토요일 22:00 crontab으로 실행

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

echo "[$(date '+%Y-%m-%d %H:%M:%S')] alpha_researcher 시작"

"$PYTHON_BIN" -m quant.alpha_researcher \
    --market "${ALPHA_MARKET:-kr}" \
    "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] alpha_researcher 완료"
