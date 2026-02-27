# FINAL_OPTIMIZATION_SPEC — 전부 적용할 작업 명세

**대상**: `/home/wlsdud5035/.openclaw/workspace` (OpenClaw Trading)  
**기준**: TRADING_AUDIT_AND_IMPROVEMENTS.md 요약 + 미적용 항목

---

## 1. 크론 래퍼 스크립트 추가

- **파일**: `scripts/run_stock_cron.sh`  
  - `run_btc_cron.sh`와 동일 패턴: `.env` + `openclaw.json` 로드 후  
    `exec .venv/bin/python3 stocks/stock_trading_agent.py "$@"`  
  - WORKSPACE, OPENCLAW_JSON, OPENCLAW_ENV 경로 동일 사용.

- **파일**: `scripts/run_us_cron.sh`  
  - 동일 패턴으로 `exec .venv/bin/python3 stocks/us_stock_trading_agent.py "$@"`

---

## 2. crontab에 KR/US/수집 항목 추가

현재 사용자 crontab에 아래 줄들을 **추가** (기존 BTC/대시보드 항목 유지).

```bash
# KR 주식 10분 매매 (평일 9~15시)
*/10 9-15 * * 1-5 /home/wlsdud5035/.openclaw/workspace/scripts/run_stock_cron.sh >> /home/wlsdud5035/.openclaw/logs/stock_trading.log 2>&1

# KR 1분 손절/익절 (평일)
* * * * 1-5 /home/wlsdud5035/.openclaw/workspace/scripts/run_stock_cron.sh check >> /home/wlsdud5035/.openclaw/logs/stock_check.log 2>&1

# KR 장전 (평일 08:00)
0 8 * * 1-5 /home/wlsdud5035/.openclaw/workspace/scripts/run_stock_cron.sh >> /home/wlsdud5035/.openclaw/logs/stock_premarket.log 2>&1
# 주의: 장전은 stock_premarket.py 실행. run_stock_cron.sh에 premarket 모드 추가하거나, 별도 명령으로 python3 stocks/stock_premarket.py 실행하도록 할 것.

# US 장전 (22:30)
30 22 * * * /home/wlsdud5035/.openclaw/workspace/scripts/run_us_cron.sh >> /home/wlsdud5035/.openclaw/logs/us_premarket.log 2>&1
# 주의: US 장전은 us_stock_premarket.py. run_us_cron.sh에 premarket 인자 또는 별도 진입점 필요.

# 일봉 수집 (평일 18:00)
0 18 * * 1-5 cd /home/wlsdud5035/.openclaw/workspace && .venv/bin/python3 stocks/stock_data_collector.py ohlcv >> /home/wlsdud5035/.openclaw/logs/stock_collector.log 2>&1
```

- **실제 적용**: `crontab -e`로 위 블록 추가하거나, `(crontab -l 2>/dev/null; echo "위 내용") | crontab -` 형태로 스크립트화.

---

## 3. run_stock_cron.sh 동작

- 인자 없음: `python3 stocks/stock_trading_agent.py` (매매 사이클)
- 인자 `check`: `python3 stocks/stock_trading_agent.py check`
- 인자 `premarket` (선택): `python3 stocks/stock_premarket.py`  
  → 크론에서는 장전용으로 `0 8 * * 1-5 ... run_stock_cron.sh premarket` 또는 별도 스크립트 호출.

---

## 4. run_us_cron.sh 동작

- 인자 없음: `python3 stocks/us_stock_trading_agent.py`
- 인자 `check`: `python3 stocks/us_stock_trading_agent.py check`
- 인자 `premarket` (선택): `python3 stocks/us_stock_premarket.py`  
  → 크론 US 장전: `30 22 * * * ... run_us_cron.sh premarket` 또는 동일 패턴.

---

## 5. common/config.py 보강

- 로그 경로는 이미 정의됨.  
- **추가**: 크론 스케줄 설명용 상수(문자열) 또는 TTL 상수 정리 (예: `MARKET_SUMMARY_TTL = 60`, `OVERVIEW_CACHE_TTL = 10`)가 다른 모듈과 맞는지 확인하고, 필요 시 config로 일원화.

---

## 6. API 폴백 보강 (이미 일부 적용됨)

- **stock_api.py**  
  - `get_stocks_overview`: 키움 `get_account_evaluation` 실패 시에도 DB 기반 가격만으로 목록 반환 (이미 try/except 있음 → 429 시 빈 live_prices로 계속 진행하는지 확인).
  - `get_stock_live_price`: 키움 실패 시 `daily_ohlcv` 최신가 폴백 — **이미 적용됨**.

- **btc_api.py / us_api.py**  
  - 예외 시 로그 + 안전한 기본값/빈 배열 반환 확인.

---

## 7. docs 보강

- **파일**: `docs/AGENT_LOG_CRON_AUDIT.md`  
  - 현재 crontab 목록, 로그 파일별 용도·최근 갱신, 크론 연동 여부, 이슈 요약 (TRADING_AUDIT 문서 1~2절 수준).

- **파일**: `docs/API.md` (선택)  
  - BTC / KR 주식 / US 주식 엔드포인트 목록과 메서드·경로·한 줄 설명.

---

## 8. Supabase (수동)

- **daily_reports**:  
  `ALTER TABLE daily_reports ADD COLUMN IF NOT EXISTS content JSONB;`  
  → Supabase SQL Editor에서 실행. (스펙 “전부 적용” 시 코드/크론만 적용하고, DB는 사용자가 실행.)

---

## 9. 적용 순서 권장

1. `scripts/run_stock_cron.sh`, `scripts/run_us_cron.sh` 생성 (run_btc_cron.sh 참고).
2. 필요 시 `run_stock_cron.sh`에 `premarket` 분기로 `stock_premarket.py` 실행, `run_us_cron.sh`에 `premarket` 분기로 `us_stock_premarket.py` 실행.
3. crontab에 위 항목 추가 (장전은 premarket 인자 또는 별도 명령으로).
4. `common/config.py` TTL/상수 정리.
5. `docs/AGENT_LOG_CRON_AUDIT.md` 작성, 필요 시 `docs/API.md` 작성.
6. API 폴백 동작 검토 및 필요 시 보강.

---

*이 스펙대로 전부 적용하면 FINAL_OPTIMIZATION 완료.*
