# execution/ — 주문 실행 레이어

SmartRouter · TWAP · VWAP · 슬리피지 추적. 실제 브로커 API와 직접 연결되는 최하위 레이어.

## 절대 규칙
- **실거래 주문 로직 변경 시 반드시 시뮬레이션 먼저** (`DRY_RUN=true`)
- `smart_router.py` 라우팅 로직 변경 시 전체 실행 경로 재검토
- 슬리피지 모델 수정 시 `slippage_tracker.py` 이력 데이터 기반 검증 필수
- 절대 `market_order()` 를 직접 호출하지 말 것 — 반드시 SmartRouter 경유

## 파일 구조
```
execution/
├── smart_router.py      # 주문 유형 자동 선택 (지정가/시장가/TWAP/VWAP) ⚠️
├── twap.py              # TWAP 분할 실행 (시간 가중 평균가)
├── vwap.py              # VWAP 분할 실행 (거래량 가중 평균가)
├── slippage_tracker.py  # 체결 슬리피지 기록 및 분석
└── README.md
```

## 실행 흐름
```
에이전트 BUY/SELL 신호
  → SmartRouter.route(order)
      ├── 소량 / 유동성 충분  → 지정가 즉시 체결
      ├── 중간 규모           → VWAP 분할 실행
      └── 대량 / 저유동성     → TWAP 시간 분산 실행
  → SlippageTracker.record(expected, actual)
```

## 전략별 사용 기준
| 전략 | 조건 | 비고 |
|------|------|------|
| 지정가 | 주문금액 < 50만원 | 즉시 체결 우선 |
| VWAP | 50만~500만원 | 거래량 패턴 추종 |
| TWAP | 500만원 초과 | 시간 균등 분할 |

## 슬리피지 모니터링
```python
# slippage_tracker.py — 체결 후 자동 기록
# Supabase trade_executions 테이블에 expected_price / actual_price 저장
# 주간 attribution 리포트에 슬리피지 비용 포함됨
```

## 테스트
```bash
cd ~/quant-agent
pytest tests/ -k "execution or router or slippage" -v
# 반드시 DRY_RUN=true 환경에서 실행
```
