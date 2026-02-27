#!/bin/bash
# Cron wrapper for US stock agent.
# - Loads env from .env + openclaw.json
# - Supports: trading(default), check, status, premarket

set -u

OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"

cd "$WORKSPACE" || exit 1

if [ -f "$OPENCLAW_ENV" ]; then
  set -a
  source "$OPENCLAW_ENV"
  set +a
fi

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

MODE="${1:-trading}"
TARGET="stocks/us_stock_trading_agent.py"

if [ "$MODE" = "premarket" ]; then
  shift
  TARGET="stocks/us_stock_premarket.py"
fi

echo "[CRON][US] $(date -Iseconds) MODE=$MODE ARGS=$*"
exec .venv/bin/python3 "$TARGET" "$@"
