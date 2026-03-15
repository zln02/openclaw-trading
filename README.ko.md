# OpenClaw Trading System

한국어 안내 문서입니다. 영문 소개용 README는 [README.md](README.md)를 참고하세요.

## 개요

OpenClaw Trading System은 OpenClaw 런타임 위에서 동작하는 3시장 자동매매/리서치 플랫폼입니다.

- BTC: 실거래
- KR 주식: 모의투자
- US 주식: DRY-RUN

핵심 목적은 단순 자동매매가 아니라, 리서치 결과가 실제 운영 파라미터로 이어지는 Research-to-Production Loop를 만드는 것입니다.

## 핵심 기능

- BTC / KR / US 3개 시장을 하나의 운영 스택으로 통합
- Level 5 리서치 루프: Alpha Researcher → Signal Evaluator → Param Optimizer
- Claude 기반 AI 에이전트 팀으로 시장 분석, 리스크 관리, 리포팅 수행
- FastAPI + React 대시보드와 Telegram 알림
- Supabase 기반 거래/포지션/리포트 저장
- 공통 env/path 로더와 헬스체크 스냅샷 기반 운영

## 빠른 시작

```bash
git clone https://github.com/zln02/openclaw-trading
cd openclaw-trading
cp btc/.env.example .env
bash scripts/split_docker_env.sh .env
docker compose up -d
```

대시보드는 `http://localhost:8080`에서 확인할 수 있습니다. Docker Compose는 `dashboard`, `btc-agent`, `kr-agent`, `us-agent`, `telegram-bot` 5개 서비스를 실행합니다.

## 시장별 운영 요약

### BTC

- 복합 스코어 기반 실거래
- RSI, 볼린저, 시장 심리, 변동성, 펀딩, OI, 레짐 필터 반영
- 포지션/손익/리스크 로그 추적

### KR Stocks

- 키움 API 기반 모의투자
- 룰 기반 60% + ML 40% 구조
- 포트폴리오, 보유 종목, 랭킹, 프리마켓 준비, 장중 체크 분리

### US Stocks

- 모멘텀 랭킹 기반 DRY-RUN
- 주요 지수 상태, 환율, 시장 데이터와 함께 검증
- 실거래 전 운영/연구/리포트 체계를 우선 고도화

## Level 5 Research Loop

리포지토리에는 리서치 결과를 실제 운영 파라미터에 반영하기 위한 루프가 포함되어 있습니다.

1. `quant/alpha_researcher.py`에서 후보 시그널 탐색
2. `quant/signal_evaluator.py`에서 IC/IR 검증
3. `quant/param_optimizer.py`에서 파라미터 자동 조정
4. 개선된 결과를 BTC / KR / US 에이전트에 반영

## AI Agent Team

에이전트 계층은 다음 역할로 구성됩니다.

- Orchestrator
- Market Analyst
- News Analyst
- Risk Manager
- Reporter

이 계층은 시장 해석, 전략 리뷰, 리스크 알림, 일일/주간 리포트 생성을 담당합니다.

## 대시보드와 알림

현재 저장소 기준으로 다음 운영 화면/알림 흐름이 존재합니다.

- BTC 대시보드: 캔들, 복합 스코어, 포지션, F&G
- KR 대시보드: 포트폴리오, 보유 종목, 모멘텀 랭킹
- US 대시보드: 지수 카드, 랭킹, DRY-RUN 포지션
- Telegram 알림: 매수/매도, 일일 리포트, 파라미터 변경, 헬스 경고

## 운영 / 보안 메모

- 경로는 `OPENCLAW_CONFIG_DIR`, `OPENCLAW_WORKSPACE_DIR`, `OPENCLAW_LOG_DIR`, `OPENCLAW_CONFIG_PATH` 기준으로 해석됩니다.
- `.env`는 더 이상 셸로 실행하지 않고 데이터로만 읽습니다.
- 헬스체크는 `~/.openclaw/logs/health_status.json`에 상태 스냅샷을 남깁니다.
- API 키, 로컬 로그, 런타임 파일은 커밋하지 않아야 합니다.
- 실거래 전에 paper / dry-run 검증을 유지하는 것이 기본 원칙입니다.

## 프로젝트 구조

```text
agents/      AI 에이전트 팀, 알림, 일일/주간 리포트
btc/         BTC 실거래 로직, 대시보드 엔트리, BTC API
common/      공통 설정, env 로더, 로깅, Telegram, Supabase
dashboard/   프론트엔드 자산
docs/        운영 문서, 스크린샷 가이드, 감사 문서
execution/   실행 품질, 라우팅, 슬리피지 추적
quant/       리서치 루프, 팩터, 리스크, 백테스트
scripts/     크론 래퍼, 헬스체크, 실행 스크립트
stocks/      KR/US 에이전트, ML, 브로커 연동, 수집기
tests/       Python 테스트
```

## 로드맵

- [x] Level 3: Adaptive Composite Signals
- [x] Level 4: Factor Model Operations (IC/IR → Weights)
- [x] Level 5: Research-to-Production Loop
- [ ] Level 6: Multi-Strategy Portfolio (Long-Short + Market Neutral)
- [ ] Level 7: On-chain DEX Arbitrage
- [ ] 외부 트레이더 연동용 Public API
- [ ] 모바일 대시보드 (React Native)

## 기여와 라이선스

- 기여: 이슈 또는 PR로 개선 사항을 제안해 주세요.
- 라이선스: [MIT](LICENSE)
