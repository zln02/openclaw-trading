#!/usr/bin/env bash
# Self-Healer 에이전트 래퍼
# crontab: */5 * * * * /home/wlsdud5035/openclaw/scripts/run_self_healer.sh >> /home/wlsdud5035/.openclaw/logs/self_healer.log 2>&1
set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
export PYTHONPATH="${WORKSPACE}:${PYTHONPATH:-}"

PYTHON_BIN="${WORKSPACE}/.venv/bin/python3"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] self_healer 실행"
"$PYTHON_BIN" "${WORKSPACE}/agents/self_healer.py" --quiet "$@"
