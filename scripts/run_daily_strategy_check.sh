#!/bin/bash
# Daily defense check — 최근 7일 승률 기반 방어 모드 점검
# crontab: 0 21 * * * /home/wlsdud5035/.openclaw/workspace/scripts/run_daily_strategy_check.sh
set -euo pipefail

cd ~/.openclaw/workspace
source .venv/bin/activate

python -m agents.strategy_reviewer --daily-check 2>&1 | tail -50
