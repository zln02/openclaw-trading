#!/bin/bash
# OpenClaw 공통 환경변수 로더. 각 cron 스크립트에서 source로 포함.
#
# 사용법:
#   source "$(dirname "$0")/load_env.sh"
#   load_openclaw_env

OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"

load_openclaw_env() {
    cd "$WORKSPACE" || exit 1

    if [ -f "$OPENCLAW_ENV" ]; then
        set -a
        source "$OPENCLAW_ENV"
        set +a
    fi

    local ENV_VARS
    ENV_VARS=$(.venv/bin/python3 -c "
import json, os
from shlex import quote
try:
    d = json.load(open('$OPENCLAW_JSON'))
except Exception:
    d = {}
for k, v in (d.get('env') or {}).items():
    if k != 'shellEnv' and isinstance(v, (str, int, float)) and not isinstance(v, bool):
        print(f'{k}={quote(str(v))}')
if not os.environ.get('TELEGRAM_BOT_TOKEN'):
    t = (d.get('channels') or {}).get('telegram', {}).get('botToken') or ''
    if t:
        print('TELEGRAM_BOT_TOKEN=' + quote(str(t)))
" 2>/dev/null)

    while IFS= read -r line; do
        export "$line" 2>/dev/null
    done <<< "$ENV_VARS"
}
