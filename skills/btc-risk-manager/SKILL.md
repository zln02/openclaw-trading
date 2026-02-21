# BTC 리스크 관리 스킬

## 핵심 원칙 (프로 트레이더 표준)
- **단일 포지션 최대:** 전체 자산의 10%
- **손절가:** 진입가 -2%
- **익절가:** 진입가 +4% (R:R = 1:2)
- **하루 최대 손실:** 전체 자산의 5% → 초과 시 봇 자동 정지
- **연속 손절 3회** → 1시간 쿨다운

## Supabase 기록 필수 항목
- trade_id, timestamp, action (BUY/SELL/HOLD)
- entry_price, exit_price, quantity
- pnl, pnl_pct, reason, confidence_score
- indicator_snapshot (JSON)
