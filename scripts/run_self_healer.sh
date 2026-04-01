#!/usr/bin/env bash
# Self-Healer 에이전트 래퍼
# crontab: */5 * * * * /home/wlsdud5035/quant-agent/scripts/run_self_healer.sh >> /home/wlsdud5035/.openclaw/logs/self_healer.log 2>&1
set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
export PYTHONPATH="${WORKSPACE}:${PYTHONPATH:-}"

# Docker 컨테이너가 마운트하는 실제 로그 경로로 덮어쓰기
# (기본 LOG_DIR은 ~/.openclaw/logs/ 이지만 Docker는 ./logs/ 를 씀)
export OPENCLAW_LOG_DIR="/home/wlsdud5035/quant-agent/logs"

PYTHON_BIN="${WORKSPACE}/.venv/bin/python3"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] self_healer 실행"
"$PYTHON_BIN" "${WORKSPACE}/agents/self_healer.py" --quiet "$@"
