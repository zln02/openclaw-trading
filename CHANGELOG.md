# Changelog

OpenClaw Trading System 변경 이력. [Keep a Changelog](https://keepachangelog.com/) 형식.

## [v6.3] — 2026-04-08

### Changed — LLM 매매 신호 의존 제거 (옵션 B)
- **BTC**: `rule_based_btc_signal()` 신규 (100점 결정론 스코어링)
  - 필수 조건: trend != DOWNTREND, F&G ≤ 55, vol_ratio > 0.3 (F&G ≤ 20 극도공포 시 0.15)
  - 가산 점수: UPTREND(+20), 극도공포(+25), 공포(+15), 거래량 급증(+15), MACD 양전(+10), RSI 과매도(+10), dRSI 양호(+10), 복합 스코어(+10), 음수 펀딩(+5), 숏 과다(+5)
  - SELL: DOWNTREND+RSI≥65 / F&G≥75 / dRSI≥70+BB%≥80
  - BUY 최소 신뢰도 65, 상한 95
- **BTC**: 메인 루프 `analyze_with_ai()` 호출 제거 → 룰 신호 단일 경로
- **BTC**: 기존 룰 기반 신호에 `source` 태그 추가 (`RULE_COMPOSITE`, `RULE_EXTREME_FEAR`, `RULE_OVERBOUGHT`, `RULE_TIMECUT`, `RULE_EXTREME_GREED`, `RULE_BB_TOP`, `RULE_TREND_REVERSAL`, `RULE_BTC`)
- **KR**: `get_trading_signal()` 회색지대 LLM 호출 분기 제거
  - rule_conf ≥ 85 → `RULE_PRIMARY`
  - 그 외 → `RULE_DEFAULT`
- **Attribution**: `WeeklyAttributionRunner._calc_source_attribution()` 추가
  - signal_source별 trades / total_pnl_pct / avg_pnl_pct / win_rate 집계
  - 주간 텔레그램 리포트에 "시그널 소스별 성과" 섹션 추가
- **Supabase**: `btc_trades`, `btc_position` 테이블에 `signal_source TEXT` 컬럼 + 인덱스 추가 (`supabase/level12_signal_source.sql`)

### Deprecated
- `btc/btc_trading_agent.py analyze_with_ai()` — 더 이상 호출하지 않음. Phase 4 페이퍼 검증 완료 후 삭제 예정
- `stocks/stock_trading_agent.py analyze_with_ai()` — 동일

### Added
- `tests/test_btc_rule_signal.py` — 12 단위 테스트 (결정론, BUY/SELL/HOLD 경계, 극도공포 거래량 면제, 신뢰도 cap 95)
- `common/llm_client.py` — 기존 prior 세션에서 untracked 상태로 방치되던 파일을 리포에 정식 포함
- `tests/test_llm_client.py` — 동반 테스트

### Fixed
- **kiwoom 환경변수 SSOT 분리** (`common/kiwoom_env.py` 신규)
  - `get_kiwoom_credentials()` 헬퍼 — `TRADING_ENV` 기반 MOCK/PROD 분기
  - or-fallback 제거 (PROD 키 누락 시 MOCK 키로 자동 대체되던 잠재 버그 제거)
  - `stocks/kiwoom_client.py __init__` 치환
  - `common/health.py check_kiwoom()` TRADING_ENV 인식
  - `tests/test_kiwoom_env.py` 6 케이스

### Rationale
- BTC 에이전트가 `analyze_with_ai()` 결과를 신호로 사용 → ANTHROPIC_API_KEY 401 시 `confidence=0` 매 사이클 SKIP. 룰 기반 fallback 부재로 장애 재현
- KR은 회색지대만 LLM 호출이었지만 `attribution.py`에 source별 PnL 추적 0건 → LLM 매매 신호의 PnL 기여도가 **단 한 번도 측정된 적 없음** (CLAUDE.md 트레이딩 원칙 #1 "측정되지 않은 정교화는 거부" 위반)
- US 에이전트는 이미 LLM 호출 0건으로 운영 중 (살아있는 반증)
- 운영 리포트(`news_analyst.get_symbol_sentiment`, `stock_premarket.py`, `agents/strategy_reviewer.py`)는 그대로 유지 — PnL 결정과 분리, 비용 미미, 운영자에게 정보 가치

### Verification
- `python -m py_compile` 4 파일 OK
- `pytest tests/` **88 passed** (76 기존 + 12 신규, 회귀 0)

### Post-Deploy Actions (운영 필수)
1. Supabase Dashboard > SQL Editor에서 `supabase/level12_signal_source.sql` 실행
2. `docker compose restart btc-agent kr-agent`
3. 1주간 모니터링:
   - `docker logs btc-agent | grep -iE "RULE_BTC|action"` → BUY/SELL/HOLD 다양 발생
   - `SELECT signal_source, COUNT(*), AVG(pnl_pct) FROM btc_trades WHERE created_at > now() - interval '7 days' GROUP BY 1`
   - `brain/equity/{btc,kr}.jsonl` 매일 갱신 확인
4. 정상 시 `analyze_with_ai()` DEPRECATED 함수 완전 삭제 (v6.4)
5. 이상 시 `git revert 0b7eebf27`
