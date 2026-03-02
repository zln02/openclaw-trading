#!/bin/bash
# Cron용 래퍼 — Trading Agent Team (5-에이전트 Claude 팀) 실행
# 사용법:
#   ./scripts/run_agent_team.sh --market btc
#   ./scripts/run_agent_team.sh --market kr --symbol 005930
#   ./scripts/run_agent_team.sh --market us --symbol AAPL
#
# crontab 예시 (BTC: 4시간마다):
#   0 */4 * * * /home/wlsdud5035/.openclaw/workspace/scripts/run_agent_team.sh --market btc >> /home/wlsdud5035/.openclaw/logs/agent_team_btc.log 2>&1

OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"

cd "$WORKSPACE" || exit 1

# .env 로드
if [ -f "$OPENCLAW_ENV" ]; then set -a; source "$OPENCLAW_ENV"; set +a; fi

# openclaw.json에서 환경변수 추출
ENV_VARS=$(.venv/bin/python3 -c "
import json, os
from shlex import quote
d = json.load(open('$OPENCLAW_JSON'))
for k, v in d.get('env', {}).items():
    if k != 'shellEnv' and isinstance(v, (str, int, float)) and not isinstance(v, bool):
        print(f'{k}={quote(str(v))}')
if not os.environ.get('TELEGRAM_BOT_TOKEN'):
    t = d.get('channels', {}).get('telegram', {}).get('botToken') or ''
    if t:
        print('TELEGRAM_BOT_TOKEN=' + quote(str(t)))
" 2>/dev/null)

while IFS= read -r line; do
    export "$line" 2>/dev/null
done <<< "$ENV_VARS"

echo "[AGENT_TEAM] $(date -Iseconds) ARGS=$@"
exec .venv/bin/python3 -m agents.trading_agent_team "$@"
