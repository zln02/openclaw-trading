#!/bin/bash
# Cron용 래퍼 — .env + openclaw.json 로드 후 btc/btc_trading_agent.py 실행 (실거래)
OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"

cd "$WORKSPACE" || exit 1

# .env 로드
if [ -f "$OPENCLAW_ENV" ]; then set -a; source "$OPENCLAW_ENV"; set +a; fi

# openclaw.json에서 환경변수 추출 (stdout은 key=value만, 에러는 /dev/null)
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

# 환경변수 설정 (export 출력이 로그에 찍히지 않도록)
while IFS= read -r line; do
    export "$line" 2>/dev/null
done <<< "$ENV_VARS"

echo "[CRON] $(date -Iseconds) ARGS=$@"
exec .venv/bin/python3 btc/btc_trading_agent.py "$@"
