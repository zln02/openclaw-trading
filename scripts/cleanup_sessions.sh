#!/bin/bash
# OpenClaw 로그/brain 정리 스크립트
WS="/home/wlsdud5035/.openclaw/workspace"

# OpenClaw 세션 로그 7일
find /home/wlsdud5035/.openclaw/sessions/ -mtime +7 -delete 2>/dev/null

# brain/news 30일
find "$WS/brain/news/" -mtime +30 -delete 2>/dev/null

# brain/daily-summary 60일
find "$WS/brain/daily-summary/" -mtime +60 -delete 2>/dev/null

# brain/market 30일
find "$WS/brain/market/" -mtime +30 -delete 2>/dev/null

# brain/improve 90일
find "$WS/brain/improve/" -mtime +90 -delete 2>/dev/null

# 에이전트 로그 7일
find "$WS/logs/" -name "*.log" -mtime +7 -delete 2>/dev/null
