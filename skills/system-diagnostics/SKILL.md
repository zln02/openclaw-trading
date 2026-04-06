# system-diagnostics

시스템 종합 진단 스킬. 서버 상태를 한눈에 파악.

## 트리거
"시스템 상태", "서버 진단", "헬스체크", "디스크 확인", "메모리 확인"

## 실행 항목

### 1. 디스크
```bash
df -h / /home
```
- 90% 이상 → 🔴 경고
- 80% 이상 → 🟡 주의

### 2. 메모리
```bash
free -m
```
- 가용 200MB 미만 → 🔴 경고

### 3. 프로세스
```bash
ps aux --sort=-%mem | head -10
ps aux | grep -E 'btc_trading|stock_trading|us_stock|openclaw-gateway|btc_dashboard' | grep -v grep
```
- 주요 프로세스(gateway, dashboard, 에이전트) 생존 확인

### 4. 크론 잡
```bash
openclaw cron list
```
- 에러 상태 잡 있으면 표시

### 5. 최근 로그
```bash
tail -10 /home/wlsdud5035/.openclaw/workspace/logs/btc_agent.log 2>/dev/null
tail -5 /home/wlsdud5035/.openclaw/workspace/logs/kr_agent.log 2>/dev/null
journalctl --user -u openclaw-gateway.service --since "1 hour ago" --no-pager | tail -10
```

### 6. 대시보드
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health 2>/dev/null
```

## 출력 포맷
```
🖥️ 시스템 진단 리포트
━━━━━━━━━━━━━━━━━━
💾 디스크: XX% (상태)
🧠 메모리: XXX MB 가용 (상태)
⚙️ 프로세스: gateway ✅ | dashboard ✅ | btc ✅ | kr ❌
📋 크론: 9개 등록, 에러 0개
📊 대시보드: HTTP 200 ✅
⚠️ 이슈: (있으면 나열)
```
