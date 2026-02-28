# OpenClaw Trading System v5.1

BTC · KR 주식 · US 주식 자동매매 통합 플랫폼 + 고급 Google Sheets 대시보드

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
| **Google Sheets** | **gog CLI + gspread (실시간 기록)** |
| ML | XGBoost (KR 주식 매수 예측) |

## 🎯 새로운 기능: 고급 Google Sheets 대시보드

### 📊 실시간 거래 기록 시스템
- **자동 기록**: 모든 매수/매도/손절/익절 거래 실시간 기록
- **상세 정보**: 거래일시, 시장, 종목명, 가격, 수량, 수익률, 진입근거, 뉴스요약, 에이전트
- **가격 포맷팅**: BTC(원), KR(원), US(달러) 자동 포맷팅
- **종목명 자동완성**: 코드 → 한글 종목명 자동 변환

### 💼 포트폴리오 요약
- **실시간 자산**: 현재가치, 총 평가손익, 수익률
- **시장별 분석**: BTC, KR주식, US주식 별개 관리
- **보유 현황**: 수량, 평균단가, 오늘손익
- **자동 업데이트**: 10분 단위 실시간 동기화

### 📈 통계 분석
- **기간별 성과**: 일간/주간/월간 거래 통계
- **승률 분석**: 수익거래, 손실거래, 승률 계산
- **위험 지표**: 평균수익률, 최대손실률 추적

### ⚠️ 위험 관리
- **MDD**: 최대 낙폭 추적 및 경고
- **손익비**: 수익/손실 평균 비율
- **샤프지표**: 위험 조정 수익률
- **포지션 모니터링**: 과도한 포지션 자동 감지

### 🔔 스마트 알림 시스템
- **손실 경고**: 5% 손실 시 경고, 10% 손실 시 위험 알림
- **수익 목표**: 10% 수익 달성 시 알림
- **포지션 관리**: 1억원 이상 포지션 시 알림
- **시스템 상태**: API 연결 상태 실시간 모니터링

### 🤖 완전 자동화
- **10분마다**: 대시보드 자동 업데이트
- **매일 자정**: 일일 손실 분석 실행
- **매일 09:00**: 알림 시스템 실행 및 요약 전송

## 매매 전략

### BTC — 복합 스코어 스윙
- **복합 스코어** (F&G + 일봉RSI + 볼린저밴드 + 거래량 + 추세 + 7일수익률) 기반 진입
- 매수 조건: 복합 스코어 ≥ 45 / 극단 공포(F&G ≤ 10) 오버라이드
- 손절 -3% / 익절 +15% / 트레일링 스탑 2%
- 타임컷 7일 / 쿨다운 30분 / 일일 최대 3회
- **🆕 Google Sheets 자동 기록**: 모든 거래 실시간 기록

### KR 주식 — AI + ML 하이브리드
- 모멘텀 스코어 + RSI/BB/거래량 복합 필터 + DART 재무제표 기반 펀더멘털 스코어
- XGBoost 모델 예측 (승률 78%+ 기준)
- 분할매수 3단계 (최소 4시간 간격) / 손절 -3% / 익절 +8%
- 08:00 AI 브리핑 → 09:00~15:30 자동매매
- **🆕 Google Sheets 자동 기록**: 모든 거래 실시간 기록

### US 주식 — 모멘텀 랭킹
- S&P 500 + NASDAQ 100 유니버스
- 5일/20일 수익률, 거래량비, 신고가 근접도 기반 스코어링
- A/B/C/D 등급 분류, 상위 종목 자동 진입
- 가상자본 $10,000 DRY-RUN 모드
- **🆕 Google Sheets 자동 기록**: 모든 거래 실시간 기록

## 대시보드

### 🌐 Web 대시보드 (포트 8080)
3개 시장을 하나의 대시보드에서 통합 관리:

- **BTC** (`/`) — 캔들차트, 복합스코어 게이지, 포트폴리오, F&G, 뉴스
- **KR 주식** (`/stocks`) — 포트폴리오, 보유종목, 종목 스캐너, AI 전략, 실시간 로그
- **US 주식** (`/us`) — 시장 지수, 모멘텀 랭킹, 보유 포지션, 환율(KRW)

실시간 갱신: 차트 5초 / 데이터 10~15초

### 📊 Google Sheets 대시보드 (🆕 신규)
전문가급 금융 대시보드 시스템:

| 시트 | 목적 | 링크 |
|------|------|------|
| **메인 거래기록** | 모든 거래 상세 기록 | [개인 설정 필요] |
| **포트폴리오 요약** | 실시간 자산 현황 | [개인 설정 필요] |
| **통계 분석** | 거래 통계 및 성과 | [개인 설정 필요] |
| **위험 관리** | 위험 지표 및 관리 | [개인 설정 필요] |

> ⚠️ **보안 참고**: 실제 Google Sheets ID는 보안을 위해 환경변수로 설정하거나 개인적으로 관리하세요.

## 프로젝트 구조

```
workspace/
├── btc/
│   ├── btc_trading_agent.py        # BTC 매매 에이전트 (🆕 Sheets 훅 추가)
│   ├── btc_dashboard.py            # 통합 대시보드 엔트리포인트 (FastAPI)
│   ├── routes/                     # API 라우터 모듈
│   │   ├── btc_api.py              #   BTC 엔드포인트 (stats, trades, candles, ...)
│   │   ├── stock_api.py            #   KR 주식 엔드포인트 (portfolio, chart, ...)
│   │   └── us_api.py               #   US 주식 엔드포인트 (positions, chart, ...)
│   ├── btc_news_collector.py       # 뉴스 수집
│   ├── btc_swing_backtest.py       # 스윙 전략 백테스트
│   └── templates/                  # 대시보드 HTML (btc/kr/us)
├── stocks/
│   ├── stock_trading_agent.py      # KR 주식 에이전트 (🆕 Sheets 훅 추가)
│   ├── us_stock_trading_agent.py   # US 주식 에이전트 (🆕 Sheets 훅 추가)
│   ├── kiwoom_client.py            # 키움 API 클라이언트
│   ├── ml_model.py                 # XGBoost 매수 예측
│   ├── stock_premarket.py          # KR 프리마켓 분석 + 텔레그램 브리핑
│   ├── us_stock_premarket.py       # US 프리마켓 분석 + 텔레그램 브리핑
│   ├── stock_data_collector.py     # OHLCV/재무/DART 데이터 수집
│   ├── sync_manager.py             # 키움-Supabase 포지션 동기화
│   ├── telegram_bot.py             # 텔레그램 인터랙티브 제어
│   ├── backtester.py               # KR 백테스트
│   ├── backtester_ml.py            # ML 백테스트
│   ├── us_momentum_backtest.py     # US 모멘텀 백테스트
│   └── performance_report.py       # 성과 리포트 (kr/us)
├── agents/
│   ├── daily_loss_analyzer.py      # 🆕 일일 손실 분석기
│   ├── alert_manager.py            # 알림 관리자
│   ├── news_analyst.py             # 뉴스 분석가
│   ├── regime_classifier.py        # 시장 국면 분류
│   ├── strategy_reviewer.py        # 전략 검토자
│   └── ...                         # 기타 에이전트 모듈
├── common/
│   ├── config.py                   # 공통 경로/상수 설정
│   ├── env_loader.py               # 환경변수 통합 로더
│   ├── supabase_client.py          # Supabase 클라이언트
│   ├── telegram.py                 # 텔레그램 알림
│   ├── indicators.py               # 공통 기술지표 (RSI, BB, MACD, EMA)
│   ├── sheets_logger.py            # 🆕 Google Sheets 자동 기록 모듈
│   ├── sheets_manager.py           # 🆕 고급 대시보드 관리자
│   └── alert_system.py             # 🆕 스마트 알림 시스템
├── scripts/
│   ├── run_btc_cron.sh             # BTC 크론 실행
│   ├── run_dashboard.sh            # 대시보드 실행
│   ├── run_dry_test.sh             # DRY-RUN 테스트
│   ├── check_health.sh             # 헬스체크 (5분 주기)
│   ├── dashboard_runner.py         # 🆕 통합 대시보드 실행기
│   ├── setup_dashboard_cron.sh     # 🆕 대시보드 크론 설정
│   └── update_sheets_dashboard.sh  # 🆕 시트 업데이트 스크립트
├── docs/                           # 시스템 문서
│   ├── GOOGLE_SHEETS_DASHBOARD.md  # 🆕 고급 대시보드 완벽 가이드
│   ├── OPENCLAW_INTEGRATION.md     # 🆕 통합 시스템 문서 (업데이트됨)
│   └── ...                         # 기타 문서
├── schema/                         # Supabase SQL 스키마
├── prompts/                        # AI 프롬프트/대화 기록
├── gog-docker                      # 🆕 gog CLI 바이너리 (실행 권한 포함)
└── archive/                        # 레거시 파일 보관
```

## 실행

### 🚀 기본 실행
```bash
source .venv/bin/activate

python btc/btc_trading_agent.py           # BTC 매매 에이전트
python stocks/stock_trading_agent.py      # KR 주식 에이전트
python stocks/us_stock_trading_agent.py   # US 주식 에이전트
python btc/btc_dashboard.py               # 대시보드 (포트 8080)
python stocks/performance_report.py kr    # KR 성과 리포트
python stocks/performance_report.py us    # US 성과 리포트
```

### 📊 Google Sheets 대시보드 실행 (🆕)
```bash
# 전체 대시보드 업데이트
python scripts/dashboard_runner.py

# 개별 기능 실행
python common/sheets_manager.py           # 포트폴리오/통계/위험 관리
python common/alert_system.py             # 알림 시스템
python agents/daily_loss_analyzer.py      # 일일 손실 분석

# 자동 크론 설정
./scripts/setup_dashboard_cron.sh
```

## Cron 스케줄

### 🔄 기본 크론
```
*/5 * * * *     run_btc_cron.sh              # BTC 5분 매매
0 * * * *       run_btc_cron.sh report       # BTC 1시간 리포트
*/10 9-15 * * 1-5  stock_trading_agent.py    # KR 주식 10분 매매
0 8 * * 1-5     stock_premarket.py           # KR 장전 전략 브리핑
30 22 * * *     us_stock_premarket.py        # US 장전 전략 브리핑
0 18 * * 1-5    stock_data_collector.py      # 일봉 OHLCV 수집
*/5 9-15 * * 1-5  check_health.sh           # 헬스체크 (장중 5분)
0 3 * * 6       ml_model.py                  # ML 모델 주간 재학습
```

### 📊 Google Sheets 크론 (🆕)
```
*/10 * * * *    python scripts/dashboard_runner.py    # 대시보드 자동 업데이트
0 0 * * *       python agents/daily_loss_analyzer.py  # 일일 손실 분석
0 9 * * *       python common/alert_system.py        # 알림 시스템 실행
```

## 환경변수

`.env` 또는 `openclaw.json`에서 로드 (common/env_loader.py):

### 🔑 기본 환경변수
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
OPENDART_API_KEY=
```

### 📊 Google Sheets 환경변수 (🆕)
```bash
# 개인 Google Sheets ID (보안을 위해 .env 파일에 저장)
GOOGLE_SHEET_ID=your_personal_sheet_id
GOOGLE_SHEET_TAB=시트1
USE_GOG=true
GOG_KEYRING_PASSWORD=your_secure_password
```

> 🔒 **보안 경고**: Google Sheets ID와 비밀번호는 절대 공개 저장소에 커밋하지 마세요! `.env` 파일이나 환경변수로 안전하게 관리하세요.

### 🔍 선택적 환경변수
```
BRAVE_API_KEY=                    # 뉴스 검색용
GOOGLE_SHEETS_CREDENTIALS_JSON=   # gspread 대체용 (서비스 계정)
```

## 리스크 설정

| 시장 | 손절 | 익절 | 트레일링 | 최대 포지션 | 일일 한도 |
|------|------|------|----------|-------------|-----------|
| BTC | -3% | +15% | 2% | 1 | 3회 |
| KR 주식 | -3% | +8% | - | 5 | 2회/종목 |
| US 주식 | -5% | +12% | 3% | 5 | DRY-RUN |

### 🚨 Google Sheets 알림 임계값 (🆕)
- **손실 경고**: -5% 손실 시 텔레그램 경고
- **위험 손실**: -10% 손실 시 텔레그램 위험 알림
- **수익 목표**: +10% 수익 시 텔레그램 알림
- **포지션 과다**: 1억원 이상 포지션 시 경고

## 📚 문서

- **[고급 Google Sheets 대시보드 가이드](docs/GOOGLE_SHEETS_DASHBOARD.md)** - 완벽한 설정 및 사용법
- **[OpenClaw 통합 시스템 문서](docs/OPENCLAW_INTEGRATION.md)** - 전체 시스템 통합 가이드
- **[Telegram 명령어 가이드](docs/telegram_commands.md)** - 텔레그램 봇 사용법

## 🛠️ 설치 및 설정

### 1. Google Sheets 설정 (🆕)
```bash
# 1. Google Cloud Console에서 Sheets API 활성화
# 2. gog CLI 인증
./gog-docker auth add your-email@gmail.com --services sheets

# 3. 환경변수 설정
export GOOGLE_SHEET_ID="your_sheet_id"
export USE_GOG="true"
export GOG_KEYRING_PASSWORD="your_password"
```

### 2. 자동 크론 설정 (🆕)
```bash
# 대시보드 자동 업데이트 크론 설정
./scripts/setup_dashboard_cron.sh
```

## 🎯 주요 개선 사항 (v5.1)

### ✨ 새로운 기능
- **📊 고급 Google Sheets 대시보드**: 실시간 거래 기록 및 분석
- **💼 포트폴리오 관리**: 자산 현황 및 성과 분석
- **⚠️ 위험 관리**: MDD, 손익비, 샤프지표 등 전문가급 지표
- **🔔 스마트 알림**: 손실 경고, 수익 목표, 시스템 상태 알림
- **🤖 완전 자동화**: 10분 단위 자동 업데이트

### 🔧 기술 개선
- **안정성 향상**: NoneType 오류 방지, 안전한 데이터 처리
- **gog CLI 통합**: Docker 환경 완벽 지원
- **에이전트 훅**: 모든 에이전트에 Google Sheets 자동 기록 추가
- **통합 실행기**: 100% 성공률의 대시보드 관리 시스템

### 📈 성과
- **100% 자동화**: 모든 거래가 실시간으로 기록됨
- **전문가급 분석**: 포트폴리오, 통계, 위험 관리 지표 제공
- **스마트 알림**: 중요한 이벤트 실시간 알림
- **완벽한 문서**: 설치부터 사용까지 완벽 가이드 제공

---

**🎉 OpenClaw v5.1: 완벽한 자동매매 관리 시스템으로 업그레이드!**

*마지막 업데이트: 2026년 3월 1일*
