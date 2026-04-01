# btc/ — BTC 자동매매 에이전트

Upbit 실거래. 10분 사이클로 10-factor 복합 점수(0–100) 계산 → 레짐 필터 → 주문 실행.

## 절대 규칙
- **실거래 코드(`btc_trading_agent.py`) 수정 시 반드시 Plan Mode 먼저**
- `DrawdownGuard` / `CircuitBreaker` 변경 시 테스트 필수
- `UPBIT_ACCESS_KEY` / `UPBIT_SECRET_KEY` 절대 로그 출력 금지
- 주문 함수 수정 후 반드시 dry-run 확인 (`DRY_RUN=true` 환경변수)

## 환경변수
```
UPBIT_ACCESS_KEY   # Upbit Open API 접근 키
UPBIT_SECRET_KEY   # Upbit Open API 비밀 키
```

## 파일 구조
```
btc/
├── btc_trading_agent.py   # 메인 에이전트 (10분 사이클, 실거래) ⚠️
├── btc_dashboard.py       # FastAPI 대시보드 서버 :8080
├── btc_ml_model.py        # BTC ML 보조 모델
├── btc_news_collector.py  # 뉴스 수집
├── btc_swing_backtest.py  # 스윙 전략 백테스트
├── routes/
│   ├── btc_api.py         # /api/btc/* 라우터
│   ├── stock_api.py       # /api/kr/* 라우터
│   └── us_api.py          # /api/us/* 라우터
├── signals/
│   ├── whale_tracker.py   # 고래 포지션 추적
│   ├── orderflow.py       # 체결 흐름 분석
│   └── arb_detector.py    # 김치 프리미엄 / 재정거래 탐지
└── strategies/
    └── funding_carry.py   # 펀딩비 캐리 전략
```

## 신호 흐름
```
10-factor 복합 점수 (0-100)
  → 레짐 분류 (BULL/BEAR/SIDEWAYS/CRISIS)
  → DrawdownGuard 통과 여부 확인
  → CircuitBreaker 상태 확인
  → Upbit 주문 실행
```

## 리스크 파일
| 파일 | 이유 |
|------|------|
| `btc_trading_agent.py` buy/sell | Upbit 실거래 직접 연결 |
| `routes/btc_api.py` | 대시보드 인증 로직 포함 |

## 테스트
```bash
cd ~/quant-agent
pytest tests/ -k "btc" -v
python btc/btc_trading_agent.py  # DRY_RUN=true 설정 후 실행
```
