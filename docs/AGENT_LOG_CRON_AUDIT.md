# AGENT_LOG_CRON_AUDIT

기준일: 2026-03-15

## 요약

- 실행 코드 루트는 `/home/wlsdud5035/openclaw`다.
- 런타임 상태와 로그는 `/home/wlsdud5035/.openclaw` 아래에 유지된다.
- 2026-03-15 작업으로 실제 사용자 crontab에 US trading 3개 항목과 `18:00 ohlcv` 수집 항목을 반영했다.
- 로그 파일은 KR/US/BTC 관련 파일이 모두 존재하며, active crontab과 로그 경로를 현재 구조 기준으로 맞췄다.

## 현재 crontab 감사

2026-03-15 기준 `crontab -l` 확인 결과:

- 활성화됨: `run_btc_cron.sh`, `run_stock_cron.sh`, `run_us_cron.sh`, `run_top_tier_cron.sh`, `check_health.sh`, `run_alpha_researcher.sh`, `run_signal_evaluator.sh`, `run_param_optimizer.sh`
- KR trading: 장중 10분 매매, 장중 1분 체크, 08:00 premarket
- US trading: 야간 15분 매매, 야간 5분 체크, 22:30 premarket
- 수집 작업:
  - 활성: `stock_data_collector.py intraday` (`*/30 9-15 * * 1-5`)
  - 활성: `stock_data_collector.py extended` (`30 16 * * 1-5`)
  - 활성: `stock_data_collector.py ohlcv` (`0 18 * * 1-5`)

## 권장 크론 블록

현재 저장소 구조 기준 권장 블록:

```cron
# KR 주식 10분 매매 (평일 9~15시)
*/10 9-15 * * 1-5 /home/wlsdud5035/openclaw/scripts/run_stock_cron.sh >> /home/wlsdud5035/.openclaw/logs/stock_trading.log 2>&1

# KR 1분 손절/익절 (평일 장중)
* 9-15 * * 1-5 /home/wlsdud5035/openclaw/scripts/run_stock_cron.sh check >> /home/wlsdud5035/.openclaw/logs/stock_check.log 2>&1

# KR 장전 (평일 08:00)
0 8 * * 1-5 /home/wlsdud5035/openclaw/scripts/run_stock_cron.sh premarket >> /home/wlsdud5035/.openclaw/logs/stock_premarket.log 2>&1

# US 장전 (평일 22:30 KST)
30 22 * * 1-5 /home/wlsdud5035/openclaw/scripts/run_us_cron.sh premarket >> /home/wlsdud5035/.openclaw/logs/us_premarket.log 2>&1

# US 매매 (평일 야간 15분)
*/15 22-23,0-5 * * 1-5 /home/wlsdud5035/openclaw/scripts/run_us_cron.sh >> /home/wlsdud5035/.openclaw/logs/us_trading.log 2>&1

# US 손절/익절 체크 (평일 야간 5분)
*/5 22-23,0-5 * * 1-5 /home/wlsdud5035/openclaw/scripts/run_us_cron.sh check >> /home/wlsdud5035/.openclaw/logs/us_check.log 2>&1

# KR 일봉 수집 (평일 18:00)
0 18 * * 1-5 cd /home/wlsdud5035/openclaw && .venv/bin/python3 stocks/stock_data_collector.py ohlcv >> /home/wlsdud5035/.openclaw/logs/stock_collector.log 2>&1
```

## 로그 파일 상태

`/home/wlsdud5035/.openclaw/logs` 최근 갱신 기준:

- 2026-03-15 14:20: `btc_trading.log`, `btc_check.log`, `phase14_signals.log`, `dashboard_sheets.log`, `alert_manager.log`
- 2026-03-15 14:15: `health_check.log`, `health_status.json`
- 2026-03-15 14:00: `hourly_briefing.log`
- 2026-03-15 00:00: `us_trading.log`, `us_check.log`, `us_premarket.log`, `stock_trading.log`, `stock_check.log`, `stock_premarket.log`, `stock_collector.log`

로그 해석:

- `btc_*`는 현재 crontab과 로그 갱신이 일치한다.
- `stock_*`는 현재 KR 크론과 로그 파일이 일치한다.
- `us_*`는 기존 로그 파일이 있었고, 2026-03-15에 active crontab도 다시 연결됐다.
- `stock_collector.log`는 2026-03-15에 `18:00 ohlcv` 작업이 active crontab에 추가됐다.

## 이슈 요약

- 이슈 1: `docs/FINAL_OPTIMIZATION_SPEC.md`는 예전 `~/.openclaw/workspace` 경로를 기준으로 적혀 있다.
- 이슈 2: 실제 active crontab은 `~/openclaw` 기준으로 통합됐고, 누락돼 있던 US trading 관련 3개 줄을 2026-03-15에 복구했다.
- 이슈 3: 샘플 crontab 파일의 구식 경로를 `~/openclaw` 기준으로 정정했다.
- 이슈 4: API 캐시 TTL이 route 파일 안에 흩어져 있어 공통 설정으로 옮겼다.

## 수동 작업

- Supabase SQL 실행: [supabase/daily_reports_content.sql](/home/wlsdud5035/openclaw/supabase/daily_reports_content.sql)

```sql
ALTER TABLE daily_reports ADD COLUMN IF NOT EXISTS content JSONB;
```
