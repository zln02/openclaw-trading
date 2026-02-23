# OpenClaw BTC 자동매매 시스템

## 시스템 구성
- **GCP e2-small** 서버 24시간 운영
- **Upbit API** 실거래 연동
- **gpt-4o-mini** AI 매매 판단
- **Supabase** 거래 로그
- **텔레그램** 실시간 알림
- **FastAPI 대시보드** (포트 8080)

## 전략
### 기본 전략
- 멀티타임프레임 (5분봉 + 1시간봉)
- RSI / MACD / 볼린저밴드
- Fear & Greed Index 연동
- 뉴스 감정분석 (CoinDesk RSS)
- 거래량 분석
- 분할매수 3단계 (1차 RSI≤45 / 2차 RSI≤38 / 3차 RSI≤30)
- 손절 -2% / 익절 +4% 자동화
- 일일 손실 한도 -5%

### 공격형 전략 (추가)
- 공포 극복: F&G ≤10 + RSI ≤25 → 강제 BUY
- 변동성 폭발: 거래량 평균 3배 이상 → 공격적 진입
- 김치 프리미엄: -2% 이하 저평가 → 매수 / +5% 과열 → 주의

## 파일 구조
```
workspace/
├── btc/
│   ├── btc_trading_agent.py     # 메인 매매 봇
│   ├── btc_indicators.py        # 기술적 지표
│   ├── btc_news_collector.py    # 뉴스 수집
│   ├── btc_risk_manager.py      # 리스크 관리
│   ├── btc_backtest.py          # 백테스트
│   └── btc_dashboard.py         # 웹 대시보드
├── scripts/
│   ├── run_btc_cron.sh          # 크론 실행 스크립트
│   └── run_dashboard.sh         # 대시보드 실행
├── schema/
│   ├── btc_trades_schema.sql    # 거래 테이블
│   └── automated_trading_schema.sql
└── README.md
```

## 실행 방법
```bash
# 매매 봇 수동 실행
python3 btc/btc_trading_agent.py

# 대시보드 실행
python3 btc/btc_dashboard.py

# 1시간 리포트 수동 발송
python3 btc/btc_trading_agent.py report
```

## Cron 설정
```
*/5 * * * * run_btc_cron.sh          # 5분마다 매매
0 * * * * run_btc_cron.sh report     # 1시간마다 리포트
```

## 환경변수 (.env)
```
UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=
SUPABASE_URL=
SUPABASE_SECRET_KEY=
OPENAI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
CRYPTOPANIC_API_KEY=
```

## 리스크 설정
| 항목 | 값 |
|------|-----|
| 분할매수 비율 | 30% / 30% / 30% |
| 손절 | -2% |
| 익절 | +4% |
| 일일 손실 한도 | -5% |
| 최소 신뢰도 | 65% |
