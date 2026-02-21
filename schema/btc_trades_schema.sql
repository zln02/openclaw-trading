-- BTC 매매 로그 (기존 automated_trading_schema.sql 에 추가하거나 Supabase SQL Editor에서 단독 실행)
-- 기존 테이블 삭제하지 않음. btc_trades만 생성.

CREATE TABLE IF NOT EXISTS btc_trades (
    id                 BIGSERIAL PRIMARY KEY,
    timestamp          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action             VARCHAR(4) NOT NULL,
    price              NUMERIC(15,0),
    rsi                NUMERIC(5,1),
    macd               NUMERIC(15,0),
    confidence         INTEGER,
    reason             TEXT,
    indicator_snapshot JSONB,
    order_raw          JSONB,
    pnl                NUMERIC(15,2),
    pnl_pct            NUMERIC(6,2)
);

-- 일별 성과 집계 뷰
CREATE OR REPLACE VIEW btc_daily_summary AS
SELECT
    DATE(timestamp) AS date,
    COUNT(*) FILTER (WHERE action = 'BUY')  AS buy_count,
    COUNT(*) FILTER (WHERE action = 'SELL') AS sell_count,
    AVG(confidence)                        AS avg_confidence,
    SUM(pnl)                                AS total_pnl
FROM btc_trades
GROUP BY DATE(timestamp)
ORDER BY date DESC;
