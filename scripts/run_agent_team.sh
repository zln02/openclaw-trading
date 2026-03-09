#!/usr/bin/env bash
# Cron용 래퍼 — Trading Agent Team (5-에이전트 Claude 팀) 실행
# 사용법:
#   ./scripts/run_agent_team.sh --market btc
#   ./scripts/run_agent_team.sh --market kr --symbol 005930
#   ./scripts/run_agent_team.sh --market us --symbol AAPL
#
# crontab 예시 (BTC: 4시간마다):
#   0 */4 * * * /home/wlsdud5035/.openclaw/workspace/scripts/run_agent_team.sh --market btc >> /home/wlsdud5035/.openclaw/logs/agent_team_btc.log 2>&1

set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"

echo "[AGENT_TEAM] $(date -Iseconds) ARGS=$@"
exec .venv/bin/python3 -m agents.trading_agent_team "$@"
