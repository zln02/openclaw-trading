# 주식 자동매매 v2.0 배포 가이드

## 파일 목록

| 파일 | 설명 | 변경 |
|------|------|------|
| `stock_trading_agent.py` | 핵심 매매 에이전트 | 전체 리팩토링 |
| `kiwoom_client.py` | 키움 API 클라이언트 | place_order 검증, 재시도, rate limit, get_current_price |
| `stock_data_collector.py` | 데이터 수집기 | 분봉 수집, 에러 핸들링 |
| `stock_premarket.py` | 장 전 분석 | AI fallback, 지표 기반 전략 |
| `migration_v2.sql` | DB 마이그레이션 | 신규 컬럼/테이블 |

## 배포 순서

### 1단계: DB 마이그레이션 (먼저!)
```
Supabase Dashboard → SQL Editor → migration_v2.sql 내용 복붙 → Run
```

확인:
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'trade_executions'
ORDER BY ordinal_position;
-- stock_name, entry_price, split_stage 있으면 OK
```

### 2단계: 기존 파일 백업
```bash
cd /home/wlsdud5035/.openclaw/workspace
cp stocks/stock_trading_agent.py stocks/stock_trading_agent.py.v1.bak
cp stocks/kiwoom_client.py stocks/kiwoom_client.py.v1.bak
cp stocks/stock_data_collector.py stocks/stock_data_collector.py.v1.bak
cp stocks/stock_premarket.py stocks/stock_premarket.py.v1.bak
```

### 3단계: 새 파일 배포
```bash
# 업로드된 파일을 stocks/ 디렉토리에 복사
cp [업로드 경로]/stock_trading_agent.py stocks/
cp [업로드 경로]/kiwoom_client.py stocks/
cp [업로드 경로]/stock_data_collector.py stocks/
cp [업로드 경로]/stock_premarket.py stocks/
```

### 4단계: 테스트
```bash
cd /home/wlsdud5035/.openclaw/workspace

# kiwoom 연결 테스트
.venv/bin/python stocks/kiwoom_client.py

# 포지션 상태 확인 (신규 기능)
.venv/bin/python stocks/stock_trading_agent.py status

# 데이터 수집 테스트
.venv/bin/python stocks/stock_data_collector.py ohlcv

# 장 전 브리핑 테스트 (AI 전략 생성)
.venv/bin/python stocks/stock_premarket.py
```

### 5단계: cron 확인
**반드시 `.venv/bin/python` 사용** — 시스템 `python3`는 yfinance 등 패키지가 없어 오류 발생 가능.

```bash
# 주식 매매 에이전트 (장 중 5분마다 예시)
*/5 9-15 * * 1-5 cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python stocks/stock_trading_agent.py >> /home/wlsdud5035/.openclaw/logs/stock_trading.log 2>&1

# 분봉 데이터 수집 (장 중 매 30분)
*/30 9-15 * * 1-5 cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python stocks/stock_data_collector.py intraday >> /home/wlsdud5035/.openclaw/logs/intraday.log 2>&1
```
확인: `crontab -l | grep stock` 후 `python3`로 되어 있으면 `.venv/bin/python`으로 변경.

## 롤백
```bash
cd /home/wlsdud5035/.openclaw/workspace
cp stocks/stock_trading_agent.py.v1.bak stocks/stock_trading_agent.py
cp stocks/kiwoom_client.py.v1.bak stocks/kiwoom_client.py
cp stocks/stock_data_collector.py.v1.bak stocks/stock_data_collector.py
cp stocks/stock_premarket.py.v1.bak stocks/stock_premarket.py
```
DB 마이그레이션은 비파괴적(ADD COLUMN IF NOT EXISTS)이므로 롤백 불필요.

## v1 → v2 핵심 변경 요약

### kiwoom_client.py
- `place_order()`: return_code 검증, 주문번호 반환, 입력값 검증, 실패 시 예외
- `get_stock_info()`: `_call_api` 통합
- `get_current_price()`: 현재가 간편 조회 추가
- 재시도 로직, rate limiting, 토큰 자동 갱신

### stock_data_collector.py
- `collect_intraday()`: 5분봉/1시간봉 수집 (NEW)
- `cleanup_old_data()`: 오래된 데이터 자동 정리 (NEW)
- 개별 종목 실패 시 전체 중단 방지
- 수집 결과 텔레그램 알림

### stock_premarket.py
- AI 실패 시 `generate_rule_based_strategy()` fallback
- 기술적 지표 기반 종목 스크리닝
- 전날 매매 결과 요약 포함
- 전략 JSON 스키마 일관성
