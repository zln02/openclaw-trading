# OpenClaw Trading System v4.1

BTC · KR 주식 · US 주식 자동매매 통합 플랫폼

## 시스템 구성

| 항목 | 스택 |
|------|------|
| 서버 | GCP e2-small (24시간) |
| BTC 거래소 | Upbit API (실거래) |
| KR 주식 | 키움증권 REST API (모의투자) |
| US 주식 | yfinance + 모멘텀 스코어링 (DRY-RUN) |
| AI 판단 | GPT-4o-mini |
| DB | Supabase (PostgreSQL) |
| 알림 | Telegram Bot |
| 대시보드 | FastAPI + Lightweight Charts (포트 8080) |
| ML | XGBoost (KR 주식 매수 예측) |

## 매매 전략

### BTC — 복합 스코어 스윙
- **복합 스코어** (F&G + 일봉RSI + 볼린저밴드 + 거래량 + 추세 + 7일수익률) 기반 진입
- 매수 조건: 복합 스코어 ≥ 45 / 극단 공포(F&G ≤ 10) 오버라이드
- 손절 -3% / 익절 +15% / 트레일링 스탑 2%
- 타임컷 7일 / 쿨다운 30분 / 일일 최대 3회

### KR 주식 — AI + ML 하이브리드
- 모멘텀 스코어 + RSI/BB/거래량 복합 필터
- XGBoost 모델 예측 (승률 78%+ 기준)
- 분할매수 3단계 / 손절 -3% / 익절 +8%
- 08:00 AI 브리핑 → 09:00~15:30 자동매매

### US 주식 — 모멘텀 랭킹
- S&P 500 + NASDAQ 100 유니버스
- 5일/20일 수익률, 거래량비, 신고가 근접도 기반 스코어링
- A/B/C/D 등급 분류, 상위 종목 자동 진입
- 가상자본 $10,000 DRY-RUN 모드

## 대시보드

3개 시장을 하나의 대시보드(포트 8080)에서 통합 관리:

- **BTC** (`/`) — 캔들차트, 복합스코어 게이지, 포지션, F&G, 뉴스
- **KR 주식** (`/stocks`) — 포트폴리오, 보유종목, 종목 스캐너, AI 전략
- **US 주식** (`/us`) — 시장 지수, 모멘텀 랭킹, 환율(KRW) 표시

실시간 갱신: 차트 5초 / 데이터 10~15초

## 프로젝트 구조

```
workspace/
├── btc/
│   ├── btc_trading_agent.py        # BTC 매매 에이전트
│   ├── btc_dashboard.py            # 통합 대시보드 (FastAPI)
│   ├── btc_news_collector.py       # 뉴스 수집
│   ├── btc_swing_backtest.py       # 스윙 전략 백테스트
│   └── templates/                  # 대시보드 HTML (btc/kr/us)
├── stocks/
│   ├── stock_trading_agent.py      # KR 주식 에이전트
│   ├── us_stock_trading_agent.py   # US 주식 에이전트
│   ├── kiwoom_client.py            # 키움 API 클라이언트
│   ├── ml_model.py                 # XGBoost 매수 예측
│   ├── backtester.py               # KR 백테스트
│   ├── performance_report.py       # 성과 리포트 (kr/us)
│   └── stock_data_collector.py     # OHLCV/재무 데이터 수집
├── common/
│   ├── env_loader.py               # 환경변수 통합 로더
│   ├── supabase_client.py          # Supabase 클라이언트
│   ├── telegram.py                 # 텔레그램 알림
│   └── indicators.py               # 공통 기술지표
├── scripts/
│   ├── run_btc_cron.sh             # BTC 크론 실행
│   └── run_dashboard.sh            # 대시보드 실행
├── schema/                         # Supabase SQL 스키마
├── supabase/                       # US 테이블 스키마
└── archive/                        # 레거시 파일 보관
```

## 실행

```bash
# 가상환경 활성화
source .venv/bin/activate

# BTC 매매 에이전트
python btc/btc_trading_agent.py

# KR 주식 에이전트
python stocks/stock_trading_agent.py

# US 주식 에이전트
python stocks/us_stock_trading_agent.py

# 대시보드 (포트 8080)
python btc/btc_dashboard.py

# 성과 리포트
python stocks/performance_report.py kr   # KR
python stocks/performance_report.py us   # US
```

## Cron 스케줄

```
*/5 * * * *   run_btc_cron.sh              # BTC 5분 매매
0 * * * *     run_btc_cron.sh report       # BTC 1시간 리포트
*/10 * * * *  stock_trading_agent.py        # KR 주식 10분 매매
0 9 * * 1-5   us_stock_trading_agent.py     # US 주식 매일 스캔
0 18 * * 1-5  stock_data_collector.py       # 일봉 OHLCV 수집
0 3 * * 6     ml_model.py                   # ML 모델 주간 재학습
```

## 환경변수

`.env` 또는 `openclaw.json`에서 로드 (common/env_loader.py):

```
UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=
SUPABASE_URL=
SUPABASE_SECRET_KEY=
OPENAI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
KIWOOM_APP_KEY=
KIWOOM_APP_SECRET=
```

## 리스크 설정

| 시장 | 손절 | 익절 | 트레일링 | 최대 포지션 | 일일 한도 |
|------|------|------|----------|-------------|-----------|
| BTC | -3% | +15% | 2% | 1 | 3회 |
| KR 주식 | -3% | +8% | - | 5 | 2회/종목 |
| US 주식 | -5% | +12% | 3% | 5 | DRY-RUN |
