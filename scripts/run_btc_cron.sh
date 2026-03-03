#!/bin/bash
# Cron용 래퍼 — .env + openclaw.json 로드 후 btc/btc_trading_agent.py 실행 (실거래)
source "$(dirname "$0")/load_env.sh"
load_openclaw_env

echo "[CRON] $(date -Iseconds) ARGS=$@"
exec .venv/bin/python3 btc/btc_trading_agent.py "$@"
