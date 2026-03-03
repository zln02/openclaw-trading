-- Level 4/5 업그레이드 — trade_executions 신규 컬럼
-- Supabase Dashboard > SQL Editor에서 실행

-- KR trade_executions
ALTER TABLE trade_executions
    ADD COLUMN IF NOT EXISTS ml_score         NUMERIC(6,3) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ml_confidence    NUMERIC(6,3) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS composite_score  NUMERIC(6,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rsi              NUMERIC(6,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS factor_snapshot  TEXT,
    ADD COLUMN IF NOT EXISTS news_sentiment   NUMERIC(6,3) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pnl_pct          NUMERIC(8,4);

-- US trade_executions (별도 테이블)
ALTER TABLE us_trade_executions
    ADD COLUMN IF NOT EXISTS factor_snapshot  TEXT,
    ADD COLUMN IF NOT EXISTS pnl_pct          NUMERIC(8,4);

-- signal IC 히스토리 (signal_evaluator 저장용)
CREATE TABLE IF NOT EXISTS signal_ic_history (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE NOT NULL,
    signal      TEXT NOT NULL,
    n           INTEGER,
    ic          NUMERIC(8,6),
    ir          NUMERIC(8,4),
    status      TEXT,
    active      BOOLEAN,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (date, signal)
);
