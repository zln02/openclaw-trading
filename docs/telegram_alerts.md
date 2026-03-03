# 텔레그램 알림 흐름 정리

알림이 너무 많이 오는 문제를 줄이기 위해 발송처·빈도·조건을 정리하고, 불필요한 발송을 수정했습니다.

---

## 1. 스케줄 기반 알림 (크론)

| 발송처 | 빈도 | 내용 | 비고 |
|--------|------|------|------|
| **dashboard_runner** → `AlertSystem.run_alert_check()` | **10분마다** | 포트폴리오 손실/수익/포지션 과다, **일일 거래 요약**, 시스템(Supabase/Telegram) 오류 | 일일 요약은 **하루 1회만** 발송하도록 수정됨 |
| **common/alert_system.py** (단독 실행) | **매일 09:00** | 위와 동일 | 크론 `0 9 * * *` |
| **daily_loss_analyzer** | **매일 00:00** | 손실 건 뉴스 검색 + 원인 분석 요약 | |
| **daily_report** (phase18-daily) | **매일 21:00** | 일일 리포트 (승률, 당일/누적 PnL, 레짐) | run_top_tier_cron.sh |
| **weekly_report** (phase18-weekly) | **일 21:00** | 주간 리포트 | run_top_tier_cron.sh |
| **phase18-alert** (alert_manager) | 크론에 등록 시 | 드로다운/ VaR/상관/거래량 스파이크 알림 | `--no-telegram` 옵션으로 발송 생략 가능 |

---

## 2. 매매/이벤트 기반 알림 (실시간)

| 발송처 | 조건 | 내용 |
|--------|------|------|
| **btc_trading_agent** | 일일 손실 한도 초과, 매수/매도 체결, 오류, 자동 되팔기, STOP 플래그 | BTC 매매 관련 |
| **stock_trading_agent** (KR) | 매수/매도 실패·체결, STOP_TRADING 플래그 | KR 매매 관련 |
| **us_stock_trading_agent** | 매매 체결, US 중지 플래그 | US 매매 관련 |
| **common/telegram** | `send_trade_alert` / `send_emergency_alert` 호출 시 | 체결/긴급 알림 (에이전트에서 호출) |
| **quant/signal_evaluator** | `run(notify=True)` 실행 시 | IC 요약 (크론 등에서 실행 시) |
| **agents/strategy_reviewer** | `run_daily_check(notify=True)` 실행 시 | 일일 전략 점검 요약 |
| **quant/risk/correlation** | 상관 스파이크/고상관 감지 시 | 상관 리스크 알림 |
| **secretary (Notion)** | Notion API 3회 실패 시 | Notion 생성/추가 실패 경고 |
| **autonomous_research** | 자율 학습 제안 생성 시 | [자율 학습 제안] 알림 |
| **stock_data_collector / premarket** | 수집/프리마켓 실행 시 | 해당 스크립트에서 발송하는 요약 |

---

## 3. 수정한 항목 (불필요/과다 알림 제거)

1. **API 상태 체크 시 테스트 메시지 제거**  
   - **문제**: `AlertSystem._check_api_status()`가 **10분마다** "🔔 OpenClaw 시스템 테스트" 메시지를 실제로 전송함.  
   - **수정**: Telegram 연결 검사만 하도록 변경. `getUpdates?limit=1`로 토큰/연결 검증만 하고, 채팅창에는 메시지를 보내지 않음.

2. **일일 거래 요약 알림을 하루 1회로 제한**  
   - **문제**: `check_daily_summary_alerts()`가 **10분마다** 실행될 때마다 "일일 거래 요약"을 보냄 (오늘 거래가 1건이라도 있으면).  
   - **수정**: `.last_daily_alert_sent` 파일로 당일 발송 여부를 기록하고, 같은 날에는 일일 요약 알림을 추가하지 않음.

---

## 4. 알림 줄이기 추가 옵션

- **10분마다 포트폴리오 알림**: 같은 종목/같은 유형(손실 경고 등)을 1시간 쿨다운 없이 반복 발송할 수 있음. 필요하면 `agents/alert_manager.py`처럼 쿨다운 키를 도입해 동일 알림 반복을 줄일 수 있음.
- **대시보드에서 알림 완전 분리**: 10분마다 알림을 돌리지 않고, **매일 09:00 단독 실행만** 사용하려면 `scripts/dashboard_runner.py`에서 `run_alert_check()` 호출을 제거하면 됨.

---

## 5. 관련 파일

- `common/telegram.py` — 공통 발송 유틸 (`send_telegram`, `send_trade_alert`, `send_emergency_alert`)
- `common/alert_system.py` — 포트폴리오/일일/시스템 알림 및 **수정된** API 체크·일일 1회 제한
- `scripts/dashboard_runner.py` — 10분마다 대시보드 업데이트 + 알림 실행
- `scripts/setup_dashboard_cron.sh` — 크론 등록 예시 (대시보드 10분, 일일 분석 0시, 알림 9시)
- `scripts/run_top_tier_cron.sh` — phase18-daily / phase18-weekly / phase18-alert
