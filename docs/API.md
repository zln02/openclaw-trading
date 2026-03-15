# API

기준일: 2026-03-15

OpenClaw 대시보드용 주요 엔드포인트 요약이다. 구현 파일은 `btc/routes/*.py` 아래에 있다.

## BTC

- `GET /api/btc/composite`: BTC 종합 점수와 포지션 요약 반환
- `GET /api/btc/portfolio`: BTC 오픈/종결 포지션과 요약 반환
- `GET /api/summary`: BTC 대시보드 상단 요약 반환
- `GET /api/btc/filters`: BTC 리스크 필터 상태 반환
- `GET /api/stats`: BTC 통계 카드 데이터 반환
- `GET /api/trades`: BTC 체결 내역 반환
- `GET /api/logs`: BTC 에이전트 로그 tail 반환
- `GET /api/news`: BTC 뉴스 목록 반환
- `GET /api/candles`: BTC 캔들 데이터 반환
- `GET /api/system`: BTC 시스템 상태 반환
- `GET /api/realtime/news`: 실시간 뉴스 스냅샷 반환
- `GET /api/realtime/orderbook`: 오더북 스냅샷 반환
- `GET /api/realtime/alt/{symbol}`: 대체 데이터 스냅샷 반환
- `GET /api/realtime/price/{symbol}`: 실시간 가격 스냅샷 반환
- `GET /api/brain`: 최신 brain 요약 반환
- `GET /api/agents/decisions`: 에이전트 의사결정 로그 반환
- `GET /api/agent-decisions`: 위와 동일한 별칭 엔드포인트
- `GET /api/decisions/{market}`: 시장별 의사결정 로그 반환
- `GET /api/agent-performance`: 에이전트 성과 지표 반환
- `GET /api/risk-metrics`: 리스크 메트릭 반환
- `GET /api/btc/decision-log`: BTC 결정 로그 반환

## KR Stocks

- `GET /api/stocks/market-summary`: KR 중심 글로벌 마켓 요약 반환
- `GET /api/stocks/overview`: 상위 종목 overview 반환
- `GET /api/stocks/price/{code}`: 단일 종목 현재가 또는 DB 폴백 가격 반환
- `GET /api/stocks/realtime/price/{code}`: 실시간 유사 가격 스냅샷 반환
- `GET /api/stocks/realtime/orderbook/{code}`: 호가 스냅샷 반환
- `GET /api/stocks/realtime/alt/{symbol}`: 대체 데이터 스냅샷 반환
- `GET /api/stocks/chart/{code}`: 차트 캔들 반환
- `GET /api/stocks/indicators/{code}`: 기술지표 반환
- `GET /api/stocks/portfolio`: KR 포트폴리오 반환
- `GET /api/stocks/daily-pnl`: 일간 손익 반환
- `GET /api/stocks/strategy`: 전략 파일 요약 반환
- `GET /api/stocks/logs`: KR 로그 tail 반환
- `GET /api/kr/composite`: KR 종합 점수 반환
- `GET /api/kr/portfolio`: KR 포트폴리오 요약 반환
- `GET /api/kr/system`: KR 시스템 상태 반환
- `GET /api/kr/top`: 최신 KR 시그널 목록 반환
- `GET /api/kr/trades`: KR 거래 내역 반환
- `GET /api/kr/positions`: KR 오픈 포지션 반환
- `GET /api/stocks/trades`: KR 거래 내역 별칭 반환

## US Stocks

- `GET /api/us/composite`: US 종합 점수 반환
- `GET /api/us/portfolio`: US 포트폴리오와 손익 요약 반환
- `GET /api/us/system`: US 시스템 상태 반환
- `GET /api/us/trades`: US 거래 내역 반환
- `GET /api/us/top`: 최신 US 시그널 반환
- `GET /api/us/positions`: US 오픈 포지션 반환
- `GET /api/us/chart/{symbol}`: US 종목 차트 반환
- `GET /api/us/logs`: US 로그 tail 반환
- `GET /api/us/market`: 미국 지수/레짐/모멘텀 요약 반환
- `GET /api/us/realtime/news`: US 뉴스 스냅샷 반환
- `GET /api/us/realtime/price/{symbol}`: US 실시간 유사 가격 반환
- `GET /api/us/realtime/alt/{symbol}`: US 대체 데이터 반환
- `GET /api/us/fx`: USD/KRW 환율 반환

## 폴백 정책

- KR `/api/stocks/overview`: Kiwoom 계좌 평가 실패 시 DB `daily_ohlcv` 가격으로 계속 응답한다.
- KR `/api/stocks/price/{code}`: Kiwoom 실패 시 최신 `daily_ohlcv.close_price`로 폴백한다.
- BTC `/api/news`, `/api/candles`, `/api/realtime/*`: 예외 시 빈 배열 또는 0 기반 기본값을 반환한다.
- US `/api/us/market`, `/api/us/portfolio`, `/api/us/realtime/*`, `/api/us/fx`: 예외 시 빈 배열 또는 안전한 기본값을 반환한다.
