-- Phase 13: execution quality / slippage tracking
-- Track execution quality as expected_price vs actual_price

CREATE TABLE IF NOT EXISTS execution_quality (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(32) NOT NULL,
    market VARCHAR(16) NOT NULL,
    side VARCHAR(8) NOT NULL,
    qty DOUBLE PRECISION NOT NULL,

    expected_price DOUBLE PRECISION NOT NULL,
    actual_price DOUBLE PRECISION NOT NULL,
    expected_notional DOUBLE PRECISION,
    actual_notional DOUBLE PRECISION,

    route VARCHAR(16) NOT NULL,
    order_type VARCHAR(16) NOT NULL,

    slippage_pct DOUBLE PRECISION,
    slippage_bps DOUBLE PRECISION,
    adverse_slippage_bps DOUBLE PRECISION,
    abs_slippage_bps DOUBLE PRECISION,
    is_valid BOOLEAN DEFAULT TRUE,

    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_execution_quality_ts
    ON execution_quality (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_execution_quality_symbol_ts
    ON execution_quality (symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_execution_quality_route_ts
    ON execution_quality (route, timestamp DESC);
