#!/bin/bash
# OpenClaw 고급 Google Sheets 대시보드 자동 업데이트 스크립트

cd /home/wlsdud5035/.openclaw/workspace
source .venv/bin/activate

# 환경변수 로드 (openclaw.json env 섹션에서 관리)
source "$(dirname "$0")/load_env.sh" 2>/dev/null && load_openclaw_env 2>/dev/null || true

# 로그 기록
echo "$(date): OpenClaw Google Sheets 대시보드 업데이트 시작" >> /var/log/openclaw_sheets.log

# 고급 관리 모듈 실행
python common/sheets_manager.py

if [ $? -eq 0 ]; then
    echo "$(date): OpenClaw Google Sheets 대시보드 업데이트 성공" >> /var/log/openclaw_sheets.log
else
    echo "$(date): OpenClaw Google Sheets 대시보드 업데이트 실패" >> /var/log/openclaw_sheets.log
fi
