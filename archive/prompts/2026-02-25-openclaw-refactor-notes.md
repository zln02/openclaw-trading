## 2026-02-25 워크스페이스 정리 / 리스크 관리 작업 메모

### 1. 오늘까지 적용된 주요 변경

- **DART 재무제표 수집 정상화**
  - `stocks/stock_data_collector.py`  
    - `collect_financials()` 복구 및 실행 → Supabase `financial_statements` 테이블에 TOP 종목 재무제표 적재.
    - `get_dart_financials()` 개선:
      - `status=013 (조회된 데이타가 없습니다)` 일 때 **직전 연도 → 직전-1년까지 폴백**.
      - 응답 코드/메시지를 경고 로그로 남기고, 유효 데이터가 있는 연도만 사용.
    - Supabase에서 `financial_statements` 스키마 확장:
      - `stock_code, stock_name, fiscal_year, revenue, operating_profit, net_income, total_assets, total_liabilities, total_equity, updated_at` + `(stock_code,fiscal_year)` 유니크 인덱스.

- **장 전 전략에 펀더멘털 연료 연결**
  - `stocks/stock_premarket.py`
    - `get_fundamental_scores()` 추가:
      - `financial_statements`에서 WATCHLIST 종목 최신 연도 기준 재무제표 로드.
      - ROE, 영업이익률, 부채비율 계산 후 0~100 점수로 정규화.
      - `score_profitability`(ROE 60% + 마진 40%), `score_safety`(부채비율 역점수), `score_fundamental`(수익성 70% + 안전성 30%) 산출.
    - `run_premarket()`에서:
      - 기술 지표(`get_stock_indicators`) + 펀더멘털 점수(`get_fundamental_scores`) 모두 계산.
    - `analyze_with_ai(...)` 프롬프트 확장:
      - `[기초 체력 (재무제표 기반 상위 종목)]` 섹션 추가, `score_fundamental` 상위 15개를 FY/ROE/부채비율과 함께 요약.
  - 현재 OpenAI 모듈 미설치로 실제 실행 시에는 **룰 기반 fallback**이 사용되지만,
    - 펀더멘털 점수 계산/로그는 이미 정상 동작.
    - OpenAI/모듈만 연결하면 **기술+펀더멘털을 모두 본 상위 종목 선별 구조**로 바로 활용 가능.

- **유령 포지션 제거용 잔고–DB 동기화 유틸리티**
  - `stocks/sync_manager.py` (신규)
    - Kiwoom 실제 보유 종목 (`KiwoomClient.get_account_evaluation().holdings`) vs Supabase `trade_executions(result='OPEN')` 비교.
    - 로직:
      - 종목별로 **실제 수량 vs DB OPEN 수량** 집계.
      - 실제 0주인데 DB에만 남아있는 경우 → `CLOSE_GHOST` 후보.
      - 그 외 수량이 어긋나는 경우 → `MISMATCH_WARN` (자동 수정 안 하고 로그만).
    - 모드:
      - `check` : 유령 포지션/수량 불일치 리포트만 출력 (DB 미변경).
      - `apply` : 유령 포지션의 `trade_id`들만 `result='CLOSED_SYNC'`로 업데이트.
    - 2026-02-25 기준 실행 결과:
      - NAVER/카카오/삼성바이오로직스 기존 OPEN 6건이 모두 유령 포지션으로 감지.
      - `apply` 실행으로 해당 6건을 `CLOSED_SYNC`로 정리 (실제 주문 없음, DB 상태만 수정).

- **텔레그램 대화형 제어 봇 초판**
  - `stocks/telegram_bot.py` (신규)
    - 환경:
      - `openclaw.json`, `.env`, `skills/kiwoom-api/.env` 로딩.
      - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 사용.
    - 기능:
      - `/status`:
        - `KiwoomClient.get_asset_summary()` 기반으로 계좌 요약 + 상위 10개 보유종목 현황 전송.
        - 인라인 버튼(⏹ / 💥 / 📊) 같이 표시.
      - `/stop`:
        - `stocks/STOP_TRADING` 플래그 파일 생성.
        - “자동매매 중지 플래그 설정됨, 에이전트에서 이 플래그를 보고 사이클 스킵 예정” 안내.
      - `/resume` 또는 `/start`:
        - `STOP_TRADING` 플래그 삭제.
      - `/sell_all`:
        - 현재는 **실제 매도는 수행하지 않고**, “안전한 전량 매도 루틴 설계 후 활성화 예정” 안내 메시지만 전송.
    - 실행:
      - `python stocks/telegram_bot.py` → getUpdates 폴링 모드로 동작.

- **기타 정리**
  - `stocks/*.py.v1.bak` 4개 삭제 (Git + `.gitignore`의 `*.v1.*` 로 대체).
  - `scripts/run_dry_test.sh` 수정:
    - 루트의 가상 경로 `btc_trading_agent.py` → 실제 위치 `btc/btc_trading_agent.py`.
    - `python3` → `.venv/bin/python` 사용으로 환경 통일.
  - DART 수집:
    - `stocks/stock_data_collector.py financials` 주기 실행으로 `financial_statements`를 최신 상태 유지.

---

### 2. 다음에 할 일(우선순위 제안)

1. **자동매매 STOP 플래그 연동**
   - 위치: `stocks/stock_trading_agent.py`
   - 내용:
     - 사이클 시작부 (`run_trading_cycle` 등)에서 `stocks/STOP_TRADING` 플래그 존재 여부를 체크.
     - 존재하면:
       - 텔레그램으로 “STOP_TRADING 플래그 감지 → 이번 사이클 스킵” 알림.
       - 해당 사이클에서 매수/매도 로직 진입 전 `return`.
   - 효과:
     - 텔레그램 `/stop` → **실제 매매 중단**으로 이어지는 end-to-end 제어 완성.

2. **/sell_all 안전 설계 + 구현**
   - 위치:
     - `stocks/telegram_bot.py`
     - `stocks/stock_trading_agent.py` 또는 별도 `stocks/emergency_actions.py`
   - 내용(안전장치 포함):
     - `/sell_all` 처리 시:
       - **1차**: 현재 보유 포지션 목록(Supabase or Kiwoom) 요약 + “정말 전량 매도할까요?” 확인용 인라인 버튼.
       - **2차**: “확인” 버튼 콜백에서만 실제 전량 매도 루틴 실행.
     - 전량 매도 루틴:
       - 현재 보유 종목 목록(`get_open_positions` + Kiwoom holdings) 기준으로,
       - 각 종목에 대해 `execute_sell` 호출 (시장가 전량).
       - 결과/실패 종목을 텔레그램으로 요약 보고.
   - 효과:
     - 급락장 등 위급 상황에서 **스마트폰으로 전량 매도** 가능 (2단계 확인으로 오조작 방지).

3. **실제 비용(수수료·거래세) 반영한 수익률 계산**
   - 위치:
     - `stocks/stock_trading_agent.py` 내 손절/익절 및 수익률 계산 로직.
   - 내용:
     - 매수·매도 각각 수수료 ~0.015% + 거래세 ~0.18~0.2%를 합산해,
       - 약 0.25% 수준의 **round-trip 비용**을 모델에 반영.
     - 손절/익절 기준:
       - 예: 손절 -2% → 실수익률 -2% 이하에서 발동되도록,
       - 익절 +5% → 비용 제외 후 +5%가 남도록 목표가를 약간 상향.
     - PnL 계산 시:
       - `(실제 체결가 - 진입가) / 진입가`에서 비용을 뺀 “실제로 손에 남는 수익률” 기준으로 리포트.
   - 효과:
     - “수수료·세금 떼고 나니 마이너스” 상황을 완화하고, 모의/실전 괴리 줄이기.

4. **헬스체크 스크립트 + 텔레그램 경보**
   - 위치: `scripts/check_health.sh` (신규) + 텔레그램 send 함수 재사용.
   - 내용:
     - 5분마다 실행:
       - `stock_trading_agent.py` 로그 파일(예: `~/.openclaw/logs/stock_agent.log`)의 **마지막 수정 시간** 체크.
       - 10분 이상 갱신이 없으면:
         - 텔레그램으로 `[시스템 중단 경보]` 전송.
     - 옵션:
       - 재시도/자동 재시작 여부는 별도 스크립트로 분리 (현재는 알림만).
   - 효과:
     - 크론/환경 꼬임, 예외로 인한 에이전트 중단을 **당일 안에 발견**할 수 있는 안전장치.

5. **문서/버전 정리**
   - 위치:
     - `stocks/STOCK_TRADING_AGENT_V2_CHANGELOG.md`
     - `WORKSPACE_CLEANUP_REPORT.md`
     - `prompts/2026-02-25-openclaw-refactor-notes.md` (이 파일)
   - 내용:
     - 이번 작업(잔고-DB 동기화, 펀더멘털 연료, 텔레그램 제어, 백업/스크립트 정리)을 V3.x 섹션으로 정리.
     - `docs/` 디렉터리를 도입해서:
       - 대시보드, 전략, 데이터 파이프라인, 안전장치(헬스체크/텔레그램 제어) 문서를 한곳에 모으는 구조 제안.

