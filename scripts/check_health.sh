#!/bin/bash
# 에이전트 헬스체크 — 5분마다 cron으로 실행
# 로그가 10분 이상 안 갱신되면 텔레그램 경보

LOG_FILE="/home/wlsdud5035/.openclaw/logs/stock_trading.log"
BOT_TOKEN="$(python3 -c "import json; d=json.load(open('/home/wlsdud5035/.openclaw/openclaw.json')); print(d.get('env',{}).get('TELEGRAM_BOT_TOKEN',''))")"
CHAT_ID="$(python3 -c "import json; d=json.load(open('/home/wlsdud5035/.openclaw/openclaw.json')); print(d.get('env',{}).get('TELEGRAM_CHAT_ID',''))")"

# 장 중인지 체크 (평일 09:00~15:30)
DAY=$(date +%u)  # 1=월 ... 7=일
HOUR=$(date +%H)
MIN=$(date +%M)
TIME=$((HOUR * 100 + MIN))

if [ "$DAY" -gt 5 ] || [ "$TIME" -lt 900 ] || [ "$TIME" -gt 1530 ]; then
    exit 0  # 장 외 시간이면 체크 안 함
fi

# 로그 파일 존재 확인
if [ ! -f "$LOG_FILE" ]; then
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="🚨 [헬스체크] 로그 파일 없음: $LOG_FILE" \
        -d parse_mode="HTML" > /dev/null
    exit 1
fi

# 마지막 수정 시간 체크
LAST_MOD=$(stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
NOW=$(date +%s)
DIFF=$(( (NOW - LAST_MOD) / 60 ))

if [ "$DIFF" -gt 10 ]; then
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="🚨 <b>[헬스체크 경보]</b>%0A주식 에이전트 로그가 ${DIFF}분째 갱신 없음%0A마지막: $(date -d @$LAST_MOD '+%H:%M:%S')%0A%0A확인 필요!" \
        -d parse_mode="HTML" > /dev/null
fi

# 대시보드 체크
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/stocks 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="🚨 <b>[헬스체크 경보]</b>%0A대시보드 응답 없음 (HTTP $HTTP_CODE)%0A재시작 필요!" \
        -d parse_mode="HTML" > /dev/null
fi

