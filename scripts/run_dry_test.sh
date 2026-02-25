#!/bin/bash
# DRY_RUN 테스트 — .env + openclaw.json env 로드 후 btc_trading_agent.py 실행
set -e
OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"
# OPENAI_API_KEY 등 .env 먼저 로드
if [ -f "$OPENCLAW_ENV" ]; then set -a; . "$OPENCLAW_ENV"; set +a; fi
# env 블록에서 문자열/숫자만 추출해 export (shellEnv 등 객체 제외)
export $(python3 -c "
import json
d = json.load(open('$OPENCLAW_JSON'))
for k, v in d.get('env', {}).items():
    if isinstance(v, (str, int, float)) and not isinstance(v, bool):
        from shlex import quote
        print(f'{k}={quote(str(v))}')
" 2>/dev/null)
export DRY_RUN=1
cd "$WORKSPACE"
exec .venv/bin/python btc/btc_trading_agent.py
