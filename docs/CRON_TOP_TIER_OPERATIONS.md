# CRON_TOP_TIER_OPERATIONS

Phase 14~18 모듈을 운영 환경에서 바로 돌릴 수 있도록 만든 크론 운용 가이드입니다.

## 1) 추가된 실행 스크립트

- `scripts/run_stock_cron.sh`
  - KR 에이전트 래퍼
  - 모드: `trading`(기본), `check`, `status`, `premarket`
- `scripts/run_us_cron.sh`
  - US 에이전트 래퍼
  - 모드: `trading`(기본), `check`, `status`, `premarket`
- `scripts/run_top_tier_cron.sh`
  - 위상별 러너
  - 모드: `phase14`, `phase15`, `phase16`, `phase18-alert`, `phase18-daily`, `phase18-weekly`, `all`
- `scripts/crontab.top_tier.sample`
  - 바로 붙여넣기 가능한 샘플 crontab

## 2) 실행 권한

```bash
chmod +x /home/wlsdud5035/.openclaw/workspace/scripts/run_stock_cron.sh
chmod +x /home/wlsdud5035/.openclaw/workspace/scripts/run_us_cron.sh
chmod +x /home/wlsdud5035/.openclaw/workspace/scripts/run_top_tier_cron.sh
```

## 3) 크론 설치

샘플 파일 내용을 crontab에 반영:

```bash
crontab -e
# => scripts/crontab.top_tier.sample 내용을 붙여넣기
```

또는 파일 기반으로 바로 적용:

```bash
crontab /home/wlsdud5035/.openclaw/workspace/scripts/crontab.top_tier.sample
```

## 4) 운영 전 수동 점검

```bash
/home/wlsdud5035/.openclaw/workspace/scripts/run_stock_cron.sh status
/home/wlsdud5035/.openclaw/workspace/scripts/run_us_cron.sh status
/home/wlsdud5035/.openclaw/workspace/scripts/run_top_tier_cron.sh phase14
/home/wlsdud5035/.openclaw/workspace/scripts/run_top_tier_cron.sh phase15
/home/wlsdud5035/.openclaw/workspace/scripts/run_top_tier_cron.sh phase16
/home/wlsdud5035/.openclaw/workspace/scripts/run_top_tier_cron.sh phase18-alert
```

## 5) 선택 환경변수

`run_top_tier_cron.sh`는 아래 값을 읽어 동작을 세밀하게 조절합니다.

- 공통
  - `KR_SYMBOL` (기본 `005930`)
  - `US_SYMBOL` (기본 `AAPL`)
- Phase 16 (13F, 어닝)
  - `SEC13F_FUND`, `SEC13F_PREV_FILE`, `SEC13F_CURR_FILE`
  - `EARNINGS_ACTUAL_EPS`, `EARNINGS_CONSENSUS_EPS`, `EARNINGS_SURPRISE_STD`
- Phase 18 알림
  - `ALERT_DRAWDOWN`, `ALERT_VAR95`, `ALERT_CORR_SHIFT`, `ALERT_VOLUME_SPIKE`

## 6) 로그 확인

```bash
tail -f /home/wlsdud5035/.openclaw/logs/phase14_signals.log
tail -f /home/wlsdud5035/.openclaw/logs/phase15_signals.log
tail -f /home/wlsdud5035/.openclaw/logs/phase16_signals.log
tail -f /home/wlsdud5035/.openclaw/logs/alert_manager.log
tail -f /home/wlsdud5035/.openclaw/logs/daily_report.log
tail -f /home/wlsdud5035/.openclaw/logs/weekly_report.log
```

## 7) 주의사항

- 13F/어닝 모델은 입력 데이터가 필요한 구조라, 관련 환경변수와 파일이 없는 경우 자동 스킵됩니다.
- 실제 주문 전환은 `stocks/us_broker.py --execute` 로직을 사용할 때만 발생하며,
  샘플 스케줄은 기본적으로 안전한 상태 점검 위주입니다.
- 타임존은 서버 OS 기준입니다. KST 환경이 아니면 cron 시간을 맞춰서 수정하세요.
