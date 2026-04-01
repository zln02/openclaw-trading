---
name: risk-check
description: >
  리스크 지표 빠른 점검. '리스크 체크', '리스크 확인', 'risk check' 요청 시 트리거.
  DrawdownGuard, PositionSizer, CircuitBreaker 상태를 확인한다.
---

## 실행 순서

1. 현재 드로우다운 수준 확인
2. 포지션 사이즈 Kelly 기준 초과 여부 확인
3. CircuitBreaker 발동 조건 근접 여부 확인
4. 이상 항목 있으면 즉시 요약 보고
5. 정상이면 '✅ 리스크 지표 정상' 한 줄로 완료

## 참조 파일

- `quant/risk/drawdown_guard.py` — 드로우다운 3단계 룰
- `quant/risk/position_sizer.py` — Kelly 분수 사이징
- `common/circuit_breaker.py` — 서킷브레이커 상태
- `quant/risk/var_model.py` — VaR 95/99%
- `quant/risk/correlation_monitor.py` — 집중 리스크

## 점검 기준

| 지표 | 경고 | 위험 |
|------|------|------|
| 일간 드로우다운 | > 1% | > 2% |
| 주간 드로우다운 | > 3% | > 5% |
| Kelly 초과 | > 1.0x | > 1.5x |
| VaR 95% | > 포지션 2% | > 포지션 3% |

## 출력 형식

```
## 리스크 점검 — YYYY-MM-DD HH:MM

| 항목 | 현재값 | 기준 | 상태 |
|------|--------|------|------|
| 일간 DD | X.X% | 2% | ✅/⚠️/🚨 |
| Kelly 비율 | X.Xx | 1.0x | ✅/⚠️/🚨 |
| CircuitBreaker | OFF/ON | - | ✅/🚨 |
| VaR 95% | X.X% | 3% | ✅/⚠️/🚨 |

[이상 항목 상세 / 또는 ✅ 리스크 지표 정상]
```
