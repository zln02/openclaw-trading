-- 주식 자동매매 v2.0 DB 마이그레이션
-- Supabase SQL Editor에서 실행

-- 1. trade_executions 신규 컬럼
ALTER TABLE trade_executions ADD COLUMN IF NOT EXISTS stock_name TEXT;
ALTER TABLE trade_executions ADD COLUMN IF NOT EXISTS entry_price NUMERIC;
ALTER TABLE trade_executions ADD COLUMN IF NOT EXISTS split_stage INTEGER DEFAULT 1;

-- 2. 분봉 테이블 (stock_data_collector.py intraday 사용 시)
CREATE TABLE IF NOT EXISTS intraday_ohlcv (
    id BIGSERIAL PRIMARY KEY,
    stock_code TEXT NOT NULL,
    datetime TIMESTAMPTZ NOT NULL,
    time_interval TEXT NOT NULL,
    open_price NUMERIC,
    high_price NUMERIC,
    low_price NUMERIC,
    close_price NUMERIC,
    volume BIGINT,
    UNIQUE(stock_code, datetime, time_interval)
);
CREATE INDEX IF NOT EXISTS idx_intraday_code_dt ON intraday_ohlcv(stock_code, datetime DESC);

-- 3. daily_reports에 content 컬럼 (stock_premarket v2가 JSON 저장 시)
ALTER TABLE daily_reports ADD COLUMN IF NOT EXISTS content TEXT;

-- 확인
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'trade_executions' ORDER BY ordinal_position;
