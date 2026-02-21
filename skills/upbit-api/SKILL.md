# Upbit API 스킬

## 환경변수 (openclaw.json에 추가 필요)
- UPBIT_ACCESS_KEY
- UPBIT_SECRET_KEY

## 라이브러리
```bash
pip install pyupbit
```

## 핵심 패턴

### 시세 조회
```python
import pyupbit
df = pyupbit.get_ohlcv("KRW-BTC", interval="minute5", count=200)
```

### 잔고 조회
```python
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
krw = upbit.get_balance("KRW")
btc = upbit.get_balance("BTC")
```

### 매수 (시장가)
```python
upbit.buy_market_order("KRW-BTC", amount_krw)
```

### 매도 (시장가)
```python
upbit.sell_market_order("KRW-BTC", amount_btc)
```

## 주의사항
- Upbit는 초당 10회 API 제한
- 최소 주문금액 5,000원
- 수수료 0.05% (매수/매도 각각)
- 모의투자 없음 → 반드시 소액 테스트 먼저
