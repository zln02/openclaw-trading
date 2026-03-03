-- btc_position 테이블 — 누락 컬럼 보완
-- Supabase Dashboard > SQL Editor에서 실행

ALTER TABLE btc_position
    ADD COLUMN IF NOT EXISTS highest_price   NUMERIC(20,0),
    ADD COLUMN IF NOT EXISTS pnl             NUMERIC(20,2),
    ADD COLUMN IF NOT EXISTS pnl_pct         NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS exit_price      NUMERIC(20,0),
    ADD COLUMN IF NOT EXISTS exit_time       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS partial_1_sold  BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS partial_2_sold  BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS partial_sold    BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS strategy        TEXT,
    ADD COLUMN IF NOT EXISTS exit_reason     TEXT,
    -- Level 5 signal context (IC 계산용)
    ADD COLUMN IF NOT EXISTS fg_value        INTEGER,
    ADD COLUMN IF NOT EXISTS rsi_d           NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS bb_pct          NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS vol_ratio_d     NUMERIC(6,3),
    ADD COLUMN IF NOT EXISTS trend           TEXT,
    ADD COLUMN IF NOT EXISTS funding_rate    NUMERIC(8,5),
    ADD COLUMN IF NOT EXISTS ls_ratio        NUMERIC(6,3),
    ADD COLUMN IF NOT EXISTS oi_ratio        NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS kimchi          NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS composite_score NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS market_regime   TEXT,
    ADD COLUMN IF NOT EXISTS atr_stop_price  NUMERIC(20,0);
