# stock_trading_agent.py v2.0 리팩토링 변경사항

## 🔴 치명적 버그 수정

### 1. 유령 포지션 방지
**이전**: 주문 실패해도 DB에 `OPEN`으로 저장됨  
**수정**: `place_order` 실패 시 바로 return → DB insert 실행 안 됨
```python
# v1 (버그)
except Exception as e:
    result = {'mock': True}
# → 이후 DB insert 계속 실행됨

# v2 (수정)
except Exception as e:
    return {'result': 'ORDER_FAILED'}
# → 여기서 함수 종료, DB insert 안 됨
```

### 2. 평균 진입가 계산
**이전**: `float(pos[0]['price'])` → 1차 매수가만 사용  
**수정**: `calc_avg_entry_price()` → 가중평균 (수량 × 가격)
```python
def calc_avg_entry_price(positions):
    total_cost = sum(price * qty for p in positions)
    total_qty = sum(qty for p in positions)
    return total_cost / total_qty
```

### 3. 동일 종목 중복 매수 차단
**이전**: 같은 종목에 BUY 신호 반복 시 무제한 매수  
**수정**: `get_position_for_stock()` → 기존 포지션 수 확인 → 최대 3차까지만

### 4. 손절/익절 종목명 표시
**이전**: `pos.get('stock_name', code)` → DB에 stock_name 없어서 코드만 표시  
**수정**: BUY 시 `stock_name` 컬럼 저장, 종목별 그룹핑 후 평균단가로 판단

---

## 🟡 주요 개선

### 5. AI 실패 시 룰 기반 fallback
**새로운 함수**: `rule_based_signal()`
- AI 키 없거나 API 오류 시 자동 전환
- RSI + BB + MACD + 거래량 + 코스피 + 주봉 추세 종합 점수
- BUY: 50점 이상 (각 조건별 10~30점)
- SELL: 2개 이상 매도 조건 충족 시

### 6. invest_ratio 제대로 적용
**이전**: `krw_balance * split_ratios[stage]` → 잔고 전체의 30%  
**수정**: `krw_balance * invest_ratio * split_ratios[stage]` → 잔고 10%의 40/35/25%

### 7. 장 전 전략 없어도 매매 가능
**이전**: `today_strategy.json` 없으면 사이클 전체 스킵  
**수정**: 전략 없으면 DB `top50_stocks`에서 종목 가져와 룰 기반 매매

### 8. yfinance 캐싱
**이전**: 종목마다 매번 yfinance 호출  
**수정**: `_cache` 딕셔너리로 사이클 내 1회만 호출

### 9. MACD 히스토그램 추가
**이전**: MACD 값만 사용  
**수정**: MACD Signal + Histogram 계산 → 추세 전환 감지력 향상

### 10. 쿨다운 시스템
**신규**: 매도 후 30분간 같은 종목 재매수 차단 (`RISK['cooldown_minutes']`)

### 11. status 명령어
**신규**: `python3 stock_trading_agent.py status` → 현재 포지션 요약

---

## 📝 DB 스키마 변경 필요

`trade_executions` 테이블에 컬럼 추가:
```sql
ALTER TABLE trade_executions ADD COLUMN IF NOT EXISTS stock_name TEXT;
ALTER TABLE trade_executions ADD COLUMN IF NOT EXISTS entry_price NUMERIC;
ALTER TABLE trade_executions ADD COLUMN IF NOT EXISTS split_stage INTEGER DEFAULT 1;
```

---

## 🔧 서버 배포 방법

```bash
# 1. 기존 파일 백업
cd /home/wlsdud5035/.openclaw/workspace
cp stocks/stock_trading_agent.py stocks/stock_trading_agent.py.bak

# 2. 새 파일 복사
cp [업로드된 파일] stocks/stock_trading_agent.py

# 3. DB 마이그레이션
# Supabase SQL Editor에서 위 ALTER TABLE 실행

# 4. 테스트 (장 외 시간에)
cd /home/wlsdud5035/.openclaw/workspace
.venv/bin/python stocks/stock_trading_agent.py status

# 5. cron은 변경 불필요 (동일한 인터페이스)
```

---

## ⚠️ 아직 남은 TODO

| 항목 | 상태 | 설명 |
|------|------|------|
| 분봉 데이터 | ❌ | daily_ohlcv만 사용 중, 5분봉 실시간 판단 불가 |
| 체결 확인 | ⚡ 부분 | 주문 응답 확인하나 실제 체결 조회는 미구현 |
| 백테스트 | ❌ | 전략 성과 검증 구조 없음 |
| 트레일링 스탑 | ⚡ 설정만 | RISK에 값 있으나 로직 미구현 (고점 추적 필요) |
| kiwoom_client.py 리팩토링 | ❌ | 전체 코드 리뷰 후 진행 |
