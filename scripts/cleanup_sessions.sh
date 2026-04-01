#!/bin/bash
# OpenClaw 세션 파일 정리 (7일 이상 된 .jsonl 파일 삭제)
SESSIONS_DIR="/home/wlsdud5035/.openclaw/agents/main/sessions"

if [ -d "$SESSIONS_DIR" ]; then
    count=$(find "$SESSIONS_DIR" -name "*.jsonl" -mtime +7 | wc -l)
    find "$SESSIONS_DIR" -name "*.jsonl" -mtime +7 -delete
    find "$SESSIONS_DIR" -name "*.jsonl.deleted.*" -mtime +3 -delete
    echo "세션 정리 완료: ${count}개 삭제"
fi

# 오래된 로그 정리 (30일 이상, 10MB 이상)
LOG_DIR="/home/wlsdud5035/.openclaw/logs"
if [ -d "$LOG_DIR" ]; then
    find "$LOG_DIR" -name "*.log.*.gz" -mtime +30 -delete 2>/dev/null
    echo "오래된 로그 정리 완료"
fi

# cron:
# 0 4 * * 0 /home/wlsdud5035/quant-agent/scripts/cleanup_sessions.sh >> /home/wlsdud5035/.openclaw/logs/cleanup.log 2>&1
