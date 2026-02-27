#!/bin/bash
# 대시보드 실행 — 환경변수 안전 로딩
OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"

cd "$WORKSPACE" || exit 1

if [ -f "$OPENCLAW_ENV" ]; then set -a; source "$OPENCLAW_ENV"; set +a; fi

ENV_VARS=$(.venv/bin/python3 -c "
import json, os
from shlex import quote
d = json.load(open('$OPENCLAW_JSON'))
for k, v in d.get('env', {}).items():
    if k != 'shellEnv' and isinstance(v, (str, int, float)) and not isinstance(v, bool):
        print(f'{k}={quote(str(v))}')
" 2>/dev/null)

while IFS= read -r line; do
    export "$line" 2>/dev/null
done <<< "$ENV_VARS"

exec .venv/bin/python3 btc/btc_dashboard.py
