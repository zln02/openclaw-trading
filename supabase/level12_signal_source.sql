-- Level 12 (v6.3) — signal_source 추적 컬럼 추가
-- 목적: LLM 매매 신호 제거 후 룰/ML/과거LLM 소스별 PnL attribution 측정
-- 실행: Supabase Dashboard > SQL Editor

-- BTC: btc_trades (매 사이클 로그) — signal_source 컬럼
ALTER TABLE btc_trades
    ADD COLUMN IF NOT EXISTS signal_source TEXT;

CREATE INDEX IF NOT EXISTS idx_btc_trades_signal_source
    ON btc_trades (signal_source);

-- BTC: btc_position (실제 포지션) — signal_source 컬럼
ALTER TABLE btc_position
    ADD COLUMN IF NOT EXISTS signal_source TEXT;

CREATE INDEX IF NOT EXISTS idx_btc_position_signal_source
    ON btc_position (signal_source);

-- NOTE: KR `trade_executions`와 US `us_trade_executions`의 `source` 컬럼은
-- supabase/level6_trade_columns.sql에서 이미 추가됨. 재사용.
-- v6.3부터 KR은 'RULE_PRIMARY'/'RULE_DEFAULT' 값만 기록되며,
-- 과거 'AI' 값은 LLM 시절 레거시로 유지됨.
