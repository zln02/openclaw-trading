-- BTC factor_snapshot 컬럼 추가
-- 매수/매도 시점의 top5 factor 값을 JSONB 로 기록
-- KR/US trade_executions.factor_snapshot 와 동일 스키마

ALTER TABLE btc_trades
    ADD COLUMN IF NOT EXISTS factor_snapshot JSONB;

COMMENT ON COLUMN btc_trades.factor_snapshot IS
    'BUY/SELL 시점 quant.factors.registry.calc_all 결과의 top5 (절댓값 정렬). HOLD 시 NULL.';
