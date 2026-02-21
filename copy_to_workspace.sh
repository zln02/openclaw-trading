#!/bin/bash
# wlsdud5035 로 SSH 접속한 뒤 이 스크립트를 실행하세요.
# 또는: sudo -u wlsdud5035 bash /home/wlsdud5035_gmail_com/btc_trading_setup/copy_to_workspace.sh

SETUP=/home/wlsdud5035_gmail_com/btc_trading_setup
WS=/home/wlsdud5035/.openclaw/workspace

cp -v "$SETUP"/*.py "$WS/"
cp -v "$SETUP"/*.sql "$WS/"
cp -rv "$SETUP"/skills/* "$WS/skills/"
echo "---"
ls -la "$WS"/*.py "$WS"/*.sql 2>/dev/null
ls -d "$WS"/skills/upbit-api "$WS"/skills/btc-indicators "$WS"/skills/btc-news-sentiment "$WS"/skills/btc-risk-manager 2>/dev/null
