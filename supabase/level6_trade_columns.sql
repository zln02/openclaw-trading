-- Level 6 업그레이드 — KR/US 거래 로그 확장 컬럼
-- Supabase Dashboard > SQL Editor에서 실행

-- KR trade_executions
ALTER TABLE trade_executions
    ADD COLUMN IF NOT EXISTS source            TEXT,
    ADD COLUMN IF NOT EXISTS drift_status      TEXT,
    ADD COLUMN IF NOT EXISTS drift_penalty     NUMERIC(8,3) DEFAULT 0;

ALTER TABLE trade_executions
    ALTER COLUMN ml_score SET DEFAULT 0,
    ALTER COLUMN ml_confidence SET DEFAULT 0,
    ALTER COLUMN composite_score SET DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_trade_executions_created_at
    ON trade_executions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_trade_executions_strategy
    ON trade_executions (strategy);

CREATE INDEX IF NOT EXISTS idx_trade_executions_source
    ON trade_executions (source);


-- US us_trade_executions
ALTER TABLE us_trade_executions
    ADD COLUMN IF NOT EXISTS ml_score          NUMERIC(8,3) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ml_confidence     NUMERIC(8,3) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS composite_score   NUMERIC(8,3) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS source            TEXT,
    ADD COLUMN IF NOT EXISTS strategy          TEXT,
    ADD COLUMN IF NOT EXISTS drift_status      TEXT,
    ADD COLUMN IF NOT EXISTS drift_penalty     NUMERIC(8,3) DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_us_trade_executions_created_at
    ON us_trade_executions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_us_trade_executions_strategy
    ON us_trade_executions (strategy);

CREATE INDEX IF NOT EXISTS idx_us_trade_executions_source
    ON us_trade_executions (source);
