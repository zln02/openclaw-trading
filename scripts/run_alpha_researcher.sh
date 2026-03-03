#!/usr/bin/env bash
# Alpha Researcher wrapper — 룰 기반 파라미터 그리드서치
# 매주 토요일 22:00 crontab으로 실행

set -euo pipefail

WORKSPACE=/home/wlsdud5035/.openclaw/workspace

cd "$WORKSPACE"
source .venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M:%S')] alpha_researcher 시작"

python -m quant.alpha_researcher \
    --market "${ALPHA_MARKET:-kr}" \
    "$@"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] alpha_researcher 완료"
