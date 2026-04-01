# agents/ — AI 전략 에이전트 팀

Claude 5-에이전트 팀 + 단독 실행 가능한 보조 에이전트 모음.

## 5-에이전트 팀 구조
```
Orchestrator (claude-opus-4-6)          ← 최종 BUY/SELL/HOLD 결정
  ├── MarketAnalyst  (claude-sonnet-4-6) ← 기술적 지표 분석
  ├── NewsAnalyst    (claude-haiku-4-5)  ← 뉴스 감성 분석
  ├── RiskManager    (claude-sonnet-4-6) ← 포지션/드로우다운 체크
  └── Reporter       (claude-haiku-4-5)  ← 텔레그램 리포트 생성
```
실행: `python -m agents.trading_agent_team --market btc`

## 규칙
- **에이전트 추가/수정 시 `agents/README.md` 반드시 동기화**
- 모델 변경 시 `common/config.py` MODEL_* 상수 통해서만 수정
- 에이전트 간 통신은 반드시 `decision_logger.py` 통해 Supabase 기록

## 파일 구조
```
agents/
├── trading_agent_team.py  # 5-에이전트 팀 오케스트레이터
├── gateway_agent.py       # 텔레그램 자연어 인터페이스 (18789 포트)
├── regime_classifier.py   # 시장 레짐 분류 (BULL/BEAR/SIDEWAYS/CRISIS)
├── news_analyst.py        # 뉴스 배치 분석 (GPT-4o / Claude 선택)
├── strategy_reviewer.py   # 일간 전략 경량 리뷰
├── daily_loss_analyzer.py # 일일 손실 분석
├── daily_report.py        # 일간 리포트 생성
├── weekly_report.py       # 주간 리포트 생성
├── alert_manager.py       # 경보 발송 관리
├── conflict_resolver.py   # 에이전트 간 신호 충돌 해소
├── decision_logger.py     # 결정 로그 → Supabase
├── agent_performance.py   # 에이전트별 성과 추적
├── self_healer.py         # 5분 헬스체크 (Docker/DB/메모리/로그)
└── README.md              # ← 에이전트 변경 시 반드시 업데이트
```

## 레짐 분류 (regime_classifier.py)
| 레짐 | 의미 | 거래 영향 |
|------|------|-----------|
| BULL | 상승장 | momentum 가중치 ↑ |
| BEAR | 하락장 | 포지션 축소 |
| SIDEWAYS | 횡보 | 평균회귀 전략 |
| CRISIS | 위기 | 전체 거래 중단 |

## 주의
- `self_healer.py` — cron 5분 주기 실행 중, 임의 비활성화 금지
- `regime_classifier.py` CRISIS 모드 — 모든 거래 파라미터 오버라이드
