#!/bin/bash
# .env + openclaw.json 둘 다 로드 (Supabase는 openclaw.json에 있음)
OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
if [ -f "$OPENCLAW_ENV" ]; then set -a; . "$OPENCLAW_ENV"; set +a; fi
export $(python3 -c "
import json
d = json.load(open('$OPENCLAW_JSON'))
for k, v in d.get('env', {}).items():
    if isinstance(v, (str, int, float)) and not isinstance(v, bool):
        from shlex import quote
        print(f'{k}={quote(str(v))}')
" 2>/dev/null)
cd /home/wlsdud5035/.openclaw/workspace
# venv 사용 (fastapi/uvicorn이 시스템에 없을 수 있음)
exec .venv/bin/python btc/btc_dashboard.py
