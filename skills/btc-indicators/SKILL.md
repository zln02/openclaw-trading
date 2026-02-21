# BTC 기술적 지표 스킬

## 라이브러리
```bash
pip install pandas ta-lib pandas-ta
```

## 필수 지표 조합 (프로 트레이더 기준)

### 트렌드 (방향)
- EMA 20, 50, 200
- MACD (12, 26, 9)

### 모멘텀 (타이밍)
- RSI 14 → 30 이하: 과매도, 70 이상: 과매수
- Stochastic RSI

### 변동성 (진입폭)
- Bollinger Bands (20, 2)
- ATR 14

## 신호 해석 규칙
- **강한 매수:** RSI < 35 + BB 하단 터치 + MACD 골든크로스
- **강한 매도:** RSI > 65 + BB 상단 터치 + MACD 데드크로스
- **중립:** 위 조건 미충족 → HOLD
