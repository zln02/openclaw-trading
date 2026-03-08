#!/bin/bash
# 에이전트 헬스체크 — 5분마다 cron으로 실행
# BTC/KR/US 각 에이전트 프로세스 및 실행 시간 체크:
#   - BTC : 24/7, 30분 이상 미실행 → 알림
#   - KR  : 평일 09:00~15:30 장중에만 체크, 30분 이상 미실행 → 알림
#   - US  : 평일 KST 22:00~06:00 장중에만 체크, 30분 이상 미실행 → 알림
# 대시보드 HTTP 체크는 별도로 유지

OPENCLAW_ROOT="/home/wlsdud5035/.openclaw"
OPENCLAW_JSON="$OPENCLAW_ROOT/openclaw.json"
OPENCLAW_ENV="$OPENCLAW_ROOT/.env"
LOG_DIR="$OPENCLAW_ROOT/logs"

# 임계치 (분)
STALE_MINUTES=30

# .env 로드
if [ -f "$OPENCLAW_ENV" ]; then set -a; source "$OPENCLAW_ENV"; set +a; fi

# openclaw.json에서 텔레그램 자격증명 추출
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$(python3 -c "
import json, sys
try:
    d = json.load(open('$OPENCLAW_JSON'))
    print(d.get('env', {}).get('TELEGRAM_BOT_TOKEN') or
          d.get('channels', {}).get('telegram', {}).get('botToken', ''))
except Exception:
    pass
" 2>/dev/null)}"

CHAT_ID="${TELEGRAM_CHAT_ID:-$(python3 -c "
import json, sys
try:
    d = json.load(open('$OPENCLAW_JSON'))
    print(d.get('env', {}).get('TELEGRAM_CHAT_ID', ''))
except Exception:
    pass
" 2>/dev/null)}"

# ── 텔레그램 전송 함수 ──────────────────────────────────────────────────
send_tg() {
    local msg="$1"
    if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then 
        echo "❌ Telegram 설정 없음: BOT_TOKEN=${BOT_TOKEN:+설정됨}, CHAT_ID=${CHAT_ID:+설정됨}"
        return
    fi
    
    # 중복 알림 방지: 같은 메시지는 10분에 한번만
    local msg_hash=$(echo "$msg" | md5sum | cut -d' ' -f1)
    local cache_file="/tmp/health_alert_cache_$msg_hash"
    local current_time=$(date +%s)
    
    if [ -f "$cache_file" ]; then
        local last_sent=$(cat "$cache_file" 2>/dev/null || echo "0")
        local time_diff=$((current_time - last_sent))
        
        # 10분(600초) 이내에 같은 알림을 보냈으면 건너뛰기
        if [ "$time_diff" -lt 600 ]; then
            echo "⏰ 중복 알림 건너뛰기 (남은 시간: $((600 - time_diff))초)"
            return
        fi
    fi
    
    # 알림 전송 및 캐시 기록
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${CHAT_ID}" \
        --data-urlencode "text=${msg}" \
        -d "parse_mode=HTML" > /dev/null
    
    echo "$current_time" > "$cache_file"
    echo "✅ Telegram 알림 전송: ${msg:0:50}..."
}

# ── 시각 계산 헬퍼 ───────────────────────────────────────────────────────
NOW=$(date +%s)
DAY=$(date +%u)   # 1=월 … 7=일
HOUR=$(date +%H)  # 00–23 (leading zero 있으면 8진수 오류 방지를 위해 10진수로 사용)
MIN=$(date +%M)
TIME=$(( 10#$HOUR * 100 + 10#$MIN ))   # HHMM 형식 (10# = 10진수 강제)

# ── 에이전트 프로세스 및 실행 시간 체크 함수 ────────────────────────────────
# 인자: 에이전트명, 로그파일, 프로세스명, [cron]
# cron=4번째 인자면 프로세스 체크 생략(크론 주기 실행 에이전트용) → 로그 갱신만 검사
# 에코: "ok" or "<분>분" or "NO_PROCESS" or "NO_LOG"
check_agent_health() {
    local agent_name="$1"
    local log_path="$2"
    local process_name="$3"
    local cron_only="${4:-}"
    
    echo "🔍 ${agent_name} 에이전트 체크 중..." >&2
    
    # 1. 프로세스 실행 확인 (크론 모드면 스킵 — US/KR은 주기 실행이라 대부분 프로세스 없음)
    if [ "$cron_only" != "cron" ]; then
        if ! pgrep -f "$process_name" > /dev/null; then
            echo "NO_PROCESS"
            return
        fi
    fi
    
    # 2. 로그 파일 확인
    if [ ! -f "$log_path" ]; then
        echo "NO_LOG"
        return
    fi
    
    # 3. 마지막 실행 시간 확인
    local last_mod diff
    last_mod=$(stat -c %Y "$log_path" 2>/dev/null || echo 0)
    diff=$(( (NOW - last_mod) / 60 ))
    
    if [ "$diff" -gt "$STALE_MINUTES" ]; then
        echo "${diff}"
    else
        echo "ok"
    fi
}

# ── 1. BTC 에이전트 체크 (24/7) ───────────────────────────────────────────
BTC_LOG="$LOG_DIR/btc_trading.log"
BTC_RESULT=$(check_agent_health "BTC" "$BTC_LOG" "btc_trading_agent.py" "cron")

echo "BTC 상태: $BTC_RESULT"

HINT="%0A%0A💬 제이한테 <b>'BTC 왜 그런지 보고 해결해'</b> 라고 하면 자동 진단할게!"
if [ "$BTC_RESULT" = "NO_PROCESS" ]; then
    send_tg "🚨 <b>[헬스체크] BTC 에이전트 미실행</b>%0A프로세스를 찾을 수 없습니다.$HINT"
elif [ "$BTC_RESULT" = "NO_LOG" ]; then
    send_tg "🚨 <b>[헬스체크] BTC</b>%0A로그 파일 없음: $BTC_LOG$HINT"
elif [ "$BTC_RESULT" != "ok" ]; then
    LAST_BTC=$(stat -c %Y "$BTC_LOG" 2>/dev/null || echo 0)
    send_tg "🚨 <b>[헬스체크] BTC 에이전트 장기 미실행</b>%0A${BTC_RESULT}분째 로그 미갱신%0A마지막 실행: $(date -d @${LAST_BTC} '+%m/%d %H:%M:%S')$HINT"
fi

# ── 2. KR 주식 에이전트 체크 (평일 09:00~15:30 장중에만, 크론 주기 실행 → 로그만 검사) ─
if [ "$DAY" -le 5 ] && [ "$TIME" -ge 900 ] && [ "$TIME" -le 1530 ]; then
    KR_LOG="$LOG_DIR/stock_trading.log"
    KR_RESULT=$(check_agent_health "KR" "$KR_LOG" "stock_trading_agent.py" "cron")
    
    echo "KR 상태: $KR_RESULT"
    
    KR_HINT="%0A%0A💬 제이한테 <b>'KR 왜 그런지 보고 해결해'</b> 라고 해봐!"
    if [ "$KR_RESULT" = "NO_PROCESS" ]; then
        send_tg "🚨 <b>[헬스체크] KR 주식 에이전트 미실행</b>%0A장중인데 프로세스를 찾을 수 없습니다.$KR_HINT"
    elif [ "$KR_RESULT" = "NO_LOG" ]; then
        send_tg "🚨 <b>[헬스체크] KR 주식</b>%0A로그 파일 없음: $KR_LOG$KR_HINT"
    elif [ "$KR_RESULT" != "ok" ]; then
        LAST_KR=$(stat -c %Y "$KR_LOG" 2>/dev/null || echo 0)
        send_tg "🚨 <b>[헬스체크] KR 주식 에이전트 장기 미실행</b>%0A${KR_RESULT}분째 로그 미갱신%0A마지막 실행: $(date -d @${LAST_KR} '+%m/%d %H:%M:%S')$KR_HINT"
    fi
else
    echo "KR 상태: 장중 아니므로 체크 생략"
fi

# ── 3. US 주식 에이전트 체크 (평일 KST 22:00~06:00 장중에만) ──────────────
# 22~23시 또는 00~06시 (자정 넘김 처리)
US_ACTIVE=0
if [ "$DAY" -le 5 ]; then
    if [ "$TIME" -ge 2200 ] || [ "$TIME" -le 600 ]; then
        US_ACTIVE=1
    fi
fi
# 일요일 22시~ 도 포함 (월요일 06:00까지니 DAY=7 22시 이후도 체크)
if [ "$DAY" -eq 7 ] && [ "$TIME" -ge 2200 ]; then
    US_ACTIVE=1
fi

if [ "$US_ACTIVE" -eq 1 ]; then
    US_LOG="$LOG_DIR/us_trading.log"
    US_RESULT=$(check_agent_health "US" "$US_LOG" "us_stock_trading_agent.py" "cron")
    
    echo "US 상태: $US_RESULT"
    
    US_HINT="%0A%0A💬 제이한테 <b>'US 왜 그런지 보고 해결해'</b> 라고 해봐!"
    if [ "$US_RESULT" = "NO_PROCESS" ]; then
        send_tg "🚨 <b>[헬스체크] US 주식 에이전트 미실행</b>%0A장중인데 프로세스를 찾을 수 없습니다.$US_HINT"
    elif [ "$US_RESULT" = "NO_LOG" ]; then
        send_tg "🚨 <b>[헬스체크] US 주식</b>%0A로그 파일 없음: $US_LOG$US_HINT"
    elif [ "$US_RESULT" != "ok" ]; then
        LAST_US=$(stat -c %Y "$US_LOG" 2>/dev/null || echo 0)
        send_tg "🚨 <b>[헬스체크] US 주식 에이전트 장기 미실행</b>%0A${US_RESULT}분째 로그 미갱신%0A마지막 실행: $(date -d @${LAST_US} '+%m/%d %H:%M:%S')$US_HINT"
    fi
else
    echo "US 상태: 장중 아니므로 체크 생략"
fi

# ── 4. 대시보드 HTTP 체크 ─────────────────────────────────────────────────
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    send_tg "🚨 <b>[헬스체크] 대시보드 응답 없음</b>%0AHTTP ${HTTP_CODE}%0A%0A💬 제이한테 <b>'대시보드 고쳐줘'</b> 라고 해봐!"
else
    echo "대시보드 상태: 정상 (HTTP 200)"
fi

# ── 5. 요약 로그 기록 ───────────────────────────────────────────────────────
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 헬스체크 완료 - BTC:$BTC_RESULT, KR:$KR_RESULT, US:$US_RESULT, 대시보드:$HTTP_CODE" >> "$LOG_DIR/health_check.log"
