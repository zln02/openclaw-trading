#!/bin/bash
# Cron용 래퍼 — .env + openclaw.json 로드 후 btc/btc_trading_agent.py 실행 (실거래)
OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"
# OPENAI_API_KEY 등 .env 먼저 로드
if [ -f "$OPENCLAW_ENV" ]; then set -a; . "$OPENCLAW_ENV"; set +a; fi
export $(.venv/bin/python -c "
import json, os
from shlex import quote
d = json.load(open('$OPENCLAW_JSON'))
for k, v in d.get('env', {}).items():
    if k != 'shellEnv' and isinstance(v, (str, int, float)) and not isinstance(v, bool):
        print(f'{k}={quote(str(v))}')
# 텔레그램: env에 없으면 channels.telegram.botToken 사용 (BTC 요약 리포트 발송용)
if not os.environ.get('TELEGRAM_BOT_TOKEN'):
    t = d.get('channels', {}).get('telegram', {}).get('botToken') or ''
    if t:
        print('TELEGRAM_BOT_TOKEN=' + quote(str(t)))
" 2>/dev/null)
# export DRY_RUN=1   # 실거래 시 주석 처리 유지
cd "$WORKSPACE"
echo "[CRON] $(date -Iseconds) USER=$(whoami) ARGS=$@ TG=$([ -n "$TELEGRAM_BOT_TOKEN" ] && echo SET || echo MISSING)" >> /home/wlsdud5035/.openclaw/logs/btc_trading.log
exec .venv/bin/python btc/btc_trading_agent.py "$@"
