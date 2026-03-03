# Trading Ops DevOps 스킬

사용자가 자동매매 시스템 문제를 보고해주거나 "왜 그런지 보고 해결해", "확인해봐", "고쳐줘" 같은 요청을 하면
이 스킬을 활용해 exec 도구로 직접 진단하고 해결해.

## 🏗️ 시스템 개요

OpenClaw 자동매매 시스템 v6.0
- BTC: Upbit 실거래 (24/7, 10분마다 cron)
- KR 주식: 키움증권 모의투자 (평일 09:00~15:30)
- US 주식: yfinance DRY-RUN (평일 KST 22:00~06:00)
- 대시보드: FastAPI + React (포트 8080, 24/7)

## 📁 컨테이너 경로 (exec 도구 사용 시)

```
workspace: /home/node/.openclaw/workspace
logs:      /home/node/.openclaw/logs
venv:      /home/node/.openclaw/workspace/.venv
brain:     /home/node/.openclaw/workspace/brain
scripts:   /home/node/.openclaw/workspace/scripts
```

## 📋 주요 로그 파일

| 에이전트 | 로그 경로 |
|---------|---------|
| BTC 매매 사이클 | `/home/node/.openclaw/logs/btc_trading.log` |
| BTC 1분 체크 | `/home/node/.openclaw/logs/btc_check.log` |
| KR 주식 매매 | `/home/node/.openclaw/logs/stock_trading.log` |
| KR 장전 스캔 | `/home/node/.openclaw/logs/stock_premarket.log` |
| US 주식 매매 | `/home/node/.openclaw/logs/us_trading.log` |
| 대시보드 | `/home/node/.openclaw/logs/dashboard.log` |
| 헬스체크 | `/home/node/.openclaw/logs/health_check.log` |
| 알림 매니저 | `/home/node/.openclaw/logs/alert_manager.log` |
| 신호 평가 | `/home/node/.openclaw/logs/signal_evaluator.log` |
| 파라미터 최적화 | `/home/node/.openclaw/logs/param_optimizer.log` |
| 레짐 분류기 | `/home/node/.openclaw/logs/regime_classifier.log` |

## ⚡ 빠른 전체 상태 확인 (가장 먼저 실행)

```bash
echo "=== 프로세스 ===" && ps aux | grep -E "btc_trading|stock_trading|us_stock|dashboard" | grep -v grep
echo "=== BTC 최근 ===" && tail -10 /home/node/.openclaw/logs/btc_trading.log 2>/dev/null || echo "로그없음"
echo "=== KR 최근 ===" && tail -5 /home/node/.openclaw/logs/stock_trading.log 2>/dev/null || echo "로그없음"
echo "=== US 최근 ===" && tail -5 /home/node/.openclaw/logs/us_trading.log 2>/dev/null || echo "로그없음"
echo "=== 대시보드 ===" && curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8080/stocks
```

## 🔧 에이전트별 진단

### BTC 에이전트 진단
```bash
# 오류 원인 파악
grep -i "error\|exception\|critical\|traceback" /home/node/.openclaw/logs/btc_trading.log | tail -30

# API 연결 확인
curl -s "https://api.upbit.com/v1/ticker?markets=KRW-BTC" | python3 -c "import json,sys; d=json.load(sys.stdin); print('Upbit OK:', d[0]['trade_price'], '원')" 2>/dev/null || echo "Upbit API 연결 실패"

# 마지막 실행 시간
stat /home/node/.openclaw/logs/btc_trading.log 2>/dev/null | grep Modify

# 크론 등록 확인
crontab -l | grep btc
```

### KR 주식 에이전트 진단
```bash
grep -i "error\|exception\|traceback" /home/node/.openclaw/logs/stock_trading.log | tail -20
tail -30 /home/node/.openclaw/logs/stock_trading.log
stat /home/node/.openclaw/logs/stock_trading.log | grep Modify
```

### US 주식 에이전트 진단
```bash
grep -i "error\|exception\|traceback" /home/node/.openclaw/logs/us_trading.log | tail -20
tail -30 /home/node/.openclaw/logs/us_trading.log
```

### 대시보드 진단
```bash
# HTTP 상태
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/stocks

# 프로세스 확인
ps aux | grep -E "dashboard|fastapi|uvicorn|gunicorn" | grep -v grep

# 포트 확인
ss -tlnp | grep 8080

# 오류 로그
grep -i "error\|exception" /home/node/.openclaw/logs/dashboard.log | tail -20
tail -20 /home/node/.openclaw/logs/dashboard.log
```

## 🔄 재시작 방법

### BTC 에이전트 즉시 실행 (크론 기다리지 않을 때)
```bash
cd /home/node/.openclaw/workspace && nohup .venv/bin/python3 btc/btc_trading_agent.py >> /home/node/.openclaw/logs/btc_trading.log 2>&1 &
echo "BTC 에이전트 시작됨, PID: $!"
```

### 대시보드 재시작
```bash
# 기존 프로세스 종료 (graceful)
pkill -f "dashboard_runner\|run_dashboard" 2>/dev/null; sleep 2
# 재시작
cd /home/node/.openclaw/workspace && nohup bash scripts/run_dashboard.sh >> /home/node/.openclaw/logs/dashboard.log 2>&1 &
sleep 3 && curl -s -o /dev/null -w "재시작 후 HTTP %{http_code}\n" http://localhost:8080/stocks
```

### KR/US 에이전트 (크론 기반 — 보통 다음 주기에 자동 실행됨)
```bash
# 크론이 살아있는지 확인
crontab -l | grep -E "stock|us_cron"

# 수동 즉시 실행 (긴급시)
cd /home/node/.openclaw/workspace && .venv/bin/python3 stocks/stock_trading_agent.py --once >> /home/node/.openclaw/logs/stock_trading.log 2>&1 &
```

## 🚨 공통 문제 & 해결책

### API 인증 오류 (401/403)
원인: API 키 만료 또는 잘못된 키
```bash
grep -i "401\|403\|unauthorized\|api key\|invalid" /home/node/.openclaw/logs/btc_trading.log | tail -10
```
→ openclaw.json의 UPBIT_ACCESS_KEY/SECRET_KEY 확인 필요. 사용자에게 키 갱신 요청.

### 네트워크 오류 (ConnectionError, Timeout)
```bash
curl -s --max-time 5 "https://api.upbit.com/v1/ticker?markets=KRW-BTC" -w "\nHTTP: %{http_code}" | tail -1
curl -s --max-time 5 "https://api.binance.com/api/v3/ping" -w "\nHTTP: %{http_code}" | tail -1
```
→ 네트워크 장애면 자동 복구 대기. 지속되면 GCP 인스턴스 재시작 필요.

### Python ImportError / ModuleNotFoundError
```bash
grep -i "importerror\|modulenotfounderror\|no module" /home/node/.openclaw/logs/btc_trading.log | tail -5
# 패키지 재설치
cd /home/node/.openclaw/workspace && .venv/bin/pip install -r requirements.txt -q
```

### 메모리/디스크 부족
```bash
free -h && df -h /home/node/.openclaw
# 오래된 로그 정리 (30일 이상)
find /home/node/.openclaw/logs -name "*.log" -mtime +30 -size +10M 2>/dev/null
```

### 포지션 불일치 (Supabase vs Upbit)
→ exec 대신 Supabase 스킬로 확인:
```bash
cd /home/node/.openclaw/workspace && .venv/bin/python3 -c "
from common.supabase_client import supabase
res = supabase.table('btc_position').select('*').eq('status', 'OPEN').execute()
for p in res.data: print(p['id'], p['entry_price'], p['quantity'], p['status'])
"
```

## 🛡️ 절대 하지 말 것
- `rm -rf` — 데이터/코드 삭제 금지
- `pkill -9 python` — 전체 프로세스 강제 종료 금지 (포지션 정리 안 됨)
- Upbit 주문 직접 취소 — 반드시 에이전트를 통해
- `git reset --hard` — 코드 변경 사항 손실
- 환경변수 직접 수정 — openclaw.json 통해 관리

## 📌 중요 설정 파일

| 파일 | 역할 |
|-----|------|
| `/home/node/.openclaw/openclaw.json` | 환경변수, API 키, 텔레그램 |
| `/home/node/.openclaw/workspace/brain/agent_params.json` | 자동 조정된 에이전트 파라미터 |
| `/home/node/.openclaw/workspace/brain/signal-ic/weights.json` | IC 기반 신호 가중치 |
| `/home/node/.openclaw/workspace/brain/alpha/best_params.json` | 그리드서치 최적 파라미터 |

## 💬 사용자 요청 처리 패턴

**"왜 안 되는지 봐줘" / "뭐가 문제야"**
→ 빠른 전체 상태 확인 exec 실행 → 오류 로그 확인 → 원인 진단 → 보고

**"고쳐줘" / "재시작해줘"**
→ 원인 파악 먼저 → 해결책 제시 → 사용자 확인 후 재시작 (포지션 있으면 특히 주의)

**"BTC 얼마야" / "포지션 확인"**
→ Upbit API 또는 대시보드 http://localhost:8080 에서 확인
```bash
curl -s "https://api.upbit.com/v1/ticker?markets=KRW-BTC" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'BTC: {d[0][\"trade_price\"]:,.0f}원 ({d[0][\"signed_change_rate\"]*100:+.2f}%)')"
```
