# OpenClaw Trading System — 종합 진단 리포트

**진단일**: 2026-03-09
**진단 모델**: Claude Opus 4.6
**코드베이스**: 125 Python, 15 JS/JSX, 10 Shell — ~26,000 LOC

---

## 전체 점수표

| 영역 | 점수 | 핵심 문제 |
|------|------|-----------|
| BTC 에이전트 | 7.5/10 | 포지션 롤백 레이스컨디션, 쿨다운 미적용, whale_tracker 미연결 |
| KR 에이전트 | 7.0/10 | RISK 하드코딩, ML 데이터 누출, Kiwoom 주문 재시도 0회 |
| US 에이전트 | 6.5/10 | yfinance 배치 미사용, 캐시 TTL 없음, log.warn() 잔존 |
| ML 모델 | 6.5/10 | 데이터 누출(line 248), SHAP IndexError 가능, 모델 버전관리 없음 |
| AI 에이전트 팀 | 7.0/10 | 타임아웃 없음, 결정 검증 없음, 도구 호출 결과 캐싱 없음 |
| 뉴스 분석 | 7.0/10 | 배치 JSON 파싱 취약, 예산 초과 가능, 재시도 없음 |
| 레짐 분류 | 7.0/10 | XGBoost 피처 순서 하드코딩, 학습 데이터 24개월 부족 |
| 전략 리뷰어 | 6.0/10 | 주간/일간 메트릭 수집 코드 80% 중복, PnL 계산 중복 |
| 시그널 평가기 | 7.5/10 | 통계적 유의성 테스트 없음, 다중 기간 IC 없음 |
| 파라미터 최적화 | 7.0/10 | 파일 경쟁 조건, 롤백 없음, 비용 미반영 |
| 알파 연구자 | 7.0/10 | 그리드 서치만(Bayesian 없음), 조기 종료 없음 |
| 팩터 귀속 | 7.0/10 | SELL만 분석, 통계 유의성 없음, 가중치 영속성 없음 |
| 리스크 관리 | 8.0/10 | drawdown_guard/position_sizer/var_model 잘 구현됨 |
| 대시보드 백엔드 | 7.5/10 | Upbit 캐시 로직 복잡, stock_api N+1 쿼리, us_api 배치 없음 |
| 대시보드 프론트 | 8.0/10 | BtcPage 잘 구현, KR/US 페이지 기능 부족, 모바일 미대응 |
| 공통 유틸 | 8.0/10 | config/logger/cache/retry 잘 구조화, 로그 로테이션 없음 |
| GitHub/CI | 3.0/10 | CI/CD 없음, Docker 없음, 테스트 없음, gitignore는 우수 |
| README | 9.0/10 | 340+ 줄, 아키텍처 다이어그램, 기술 스택 완비 |

---

## 시스템 전체 크리티컬 이슈 TOP 10

### 1. PnL 계산 로직 5곳 이상 중복
- `strategy_reviewer.py`, `daily_loss_analyzer.py`, `param_optimizer.py`, `daily_report.py`, `attribution.py`
- 각각 다른 컬럼명 사용 (`pnl`, `pnl_pct`, `price/entry_price`)
- **위험**: 스키마 변경 시 일부만 수정되어 불일치 발생

### 2. ML 데이터 누출 (ml_model.py:248)
- `closes[i + target_days]` 미래 데이터 참조 가능
- 경계 검사 없음 → 학습 성능 과대평가

### 3. Kiwoom 주문 재시도 0회 (kiwoom_client.py:479)
- `place_order()` 호출 시 `retries=0`
- 네트워크 순단 시 주문 실패 → 복구 불가

### 4. BTC 포지션 롤백 레이스컨디션 (btc_trading_agent.py:956-983)
- 매수 → DB 저장 실패 → 즉시 패닉 매도
- 가격 슬리피지 위험, 대기 시간 없음

### 5. 뉴스 배치 JSON 파싱 (news_analyst.py:323)
- `text.find("[")` — 이스케이프된 브래킷 미처리
- 전체 배치 실패 시 폴백 없음 (개별 처리로 전환해야 함)

### 6. CI/CD 완전 부재
- GitHub Actions 없음, Docker 없음, 테스트 없음
- 코드 품질 게이트 없이 main에 직접 푸시

### 7. 파일 기반 상태 관리 경쟁 조건
- alert_manager: `/tmp/openclaw_alert_cooldown` (프로세스 간 경쟁)
- param_optimizer: `weights.json` 동시 읽기/쓰기
- telegram.py: `.telegram_info_buffer.json` 비원자적 쓰기

### 8. XGBoost 레짐 모델 피처 순서 하드코딩 (regime_classifier.py:314)
- 학습과 예측 시 피처 순서 불일치 가능
- 명시적 검증 없음

### 9. 하드코딩된 임계값 산재
- drawdown_guard: 일간 -2%, 주간 -5%, 월간 -10%
- alert_manager: drawdown <= -0.03, var_95 >= 0.025
- 모두 config.py로 이동 필요

### 10. 로그 로테이션 없음
- `common/logger.py` — RotatingFileHandler 미사용
- 디스크 공간 무한 증가 가능 (현재 49GB 중 28GB 사용)

---

## 아키텍처 레벨 문제

### 데이터 일관성
- 컬럼명 불일치: `price` vs `entry_price` vs `buy_price`
- PnL 스키마: `pnl` vs `pnl_pct` vs `pnl_krw`
- factor_snapshot: JSON 스키마 미정의

### 에러 핸들링
- Supabase 쿼리 실패 → 빈 리스트 반환 (에이전트 결정 누락)
- LLM API 실패 → 휴리스틱 폴백 (신호 품질 저하)
- yfinance 실패 → 캐시 데이터 사용 (가격 노후화)

### 테스트
- 유닛 테스트: 0
- 통합 테스트: 0
- 백테스트만 존재 (quant/backtest/)

---

## Sonnet 구현 태스크 분류

아래 4개 파일에 Sonnet용 상세 구현 명세를 작성:

1. `01_critical_bugfixes.md` — 크리티컬 버그 수정 (P0)
2. `02_agent_improvements.md` — 에이전트 + 퀀트 개선 (P1)
3. `03_dashboard_improvements.md` — 대시보드 + API 개선 (P1)
4. `04_infra_cicd.md` — CI/CD + Docker + 테스트 (P2)
