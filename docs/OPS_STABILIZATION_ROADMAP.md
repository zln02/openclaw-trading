# Ops Stabilization Roadmap

실전 투입 전 운영 안정화와 검증 강화를 위한 작업 로드맵.

## 목표

- 시스템이 죽지 않게 만들기
- 잘못된 주문이 나가지 않게 만들기
- 실전 확대 전에 운영 상태를 재현 가능하게 만들기

## 현재 판단

- 전략/기능 폭: 높음
- 운영 자동화: 중상
- 리스크 관리: 중상
- 테스트/회귀 안정성: 중간 이하
- 실거래 신뢰성: BTC는 중상, KR은 모의 운영 수준, US는 DRY-RUN

핵심 약점은 전략 자체보다 운영 안정성과 회귀 검증 부족이다.

## 실전 투입 전 체크리스트

1. BTC/KR/US 각각 `정상`, `API 실패`, `데이터 누락`, `DB 실패` 시 동작을 문서화한다.
2. `scripts/check_health.sh` 기준 경고가 실제 텔레그램으로 오는지 검증한다.
3. `drawdown guard`, `drift gate`, `target weight`, `market allocation` 이 실제 주문 차단에 반영되는지 점검한다.
4. 리포트 숫자와 Supabase 저장값이 서로 맞는지 샘플 대조한다.
5. BTC 실거래에서 주문 실패, 부분 체결, 재시도 케이스 로그를 확인한다.
6. KR 모의투자에서 매수, 매도, 청산 `pnl_pct` 저장 누락이 없는지 확인한다.
7. US는 실거래 전환 없이 DRY-RUN 유지 상태를 점검한다.
8. 아래 산출물 최신성을 확인한다.
   - `brain/risk/latest_snapshot.json`
   - `brain/ml/drift_report.json`
   - `brain/ml/us/drift_report.json`
   - `brain/portfolio/market_allocation.json`
   - `brain/portfolio/target_weights.json`
9. 텔레그램 명령 결과가 실제 운영 상태와 일치하는지 확인한다.
10. `.env`, API 키, OAuth secret, Supabase 키 하드코딩이 없는지 재점검한다.
11. 장애 복구 절차를 문서화한다.
12. 최근 2주 로그에서 반복 에러 패턴을 정리한다.
13. 신규 기능은 실거래 판단에서 제외 유지한다.
    - long/short
    - DEX arb
    - mobile
    - webhook/push

## 가장 위험한 구멍 5개

1. 테스트 커버리지가 전체 주문 경로와 크론 체인을 충분히 덮지 못한다.
2. 운영 제어가 `scripts`, `cron`, `telegram`, `brain` 파일로 분산돼 있다.
3. 외부 API, Supabase, 네트워크 실패 시 degraded mode가 많고 강제 safe mode 기준이 약하다.
4. 실전/모의/DRY-RUN 경계가 코드상 존재하지만 운영 레벨에서 더 강하게 분리되지 않았다.
5. 일부 고급 기능은 구조만 있고 장기 운영 검증이 부족하다.

## 1개월 로드맵

### 1주차: 운영 안정화

- health 결과를 safe mode 와 연결
- Supabase/API 실패 시 시장별 거래 차단 기준 추가
- STOP/PAUSE/health 제어를 하나의 운영 경로로 통합
- 장애 복구 런북 작성

### 2주차: 검증 강화

- 시장별 핵심 경로 통합 테스트 추가
- 주문, 청산, 리포트, 리스크 가드 회귀 테스트 추가
- cron 체인 smoke test 추가
- 리포트 숫자 검증 스크립트 추가

### 3주차: 구조 정리

- OpenClaw 운영 명령 허브 정리
- `agents/` 를 운영 필수와 실험용으로 분리
- `scripts` 와 공통 함수 중복 제거
- 운영 산출물 freshness 기준 정식화

### 4주차: 실전성 강화

- BTC 실거래 예외 처리 강화
- KR 모의 성과 검증 리포트 정례화
- US DRY-RUN 성과 기준선 정리
- Claude 계층은 리뷰/리스크 승인 용도로 제한 연결

## 우선순위

1. 안 죽게 만들기
2. 잘못 사지 않게 만들기
3. 그다음 더 똑똑하게 만들기

## 바로 효과 큰 범위

반나절에서 1일 안에 처리 가능한 최소 고효율 작업:

- 외부 API/Supabase 실패 시 safe mode
- STOP/PAUSE/health 운영 제어 통합
- health 결과를 실제 거래 차단과 연결

## 참고 파일

- `scripts/check_health.sh`
- `stocks/telegram_bot.py`
- `btc/btc_trading_agent.py`
- `stocks/stock_trading_agent.py`
- `stocks/us_stock_trading_agent.py`
- `common/risk_snapshot.py`
- `agents/alert_manager.py`
