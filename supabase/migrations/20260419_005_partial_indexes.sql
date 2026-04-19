-- Phase 5-E Step 5: 추가 인덱스 (부분 인덱스 중심)
-- 자주 쓰는 조회 패턴 가속

-- btc_position: status='OPEN' 빠른 lookup (포지션 존재 여부 매 사이클 체크)
CREATE INDEX IF NOT EXISTS idx_btc_position_open
    ON public.btc_position (id)
    WHERE status = 'OPEN';

-- trade_executions: result='OPEN' 미결 포지션 조회
CREATE INDEX IF NOT EXISTS idx_trade_executions_open
    ON public.trade_executions (stock_code, created_at DESC)
    WHERE result = 'OPEN';

-- us_trade_executions: result='OPEN' 미결 포지션 조회
CREATE INDEX IF NOT EXISTS idx_us_trade_executions_open
    ON public.us_trade_executions (symbol, created_at DESC)
    WHERE result = 'OPEN';

-- btc_trades.timestamp DESC 순 조회 (대시보드)
CREATE INDEX IF NOT EXISTS idx_btc_trades_ts
    ON public.btc_trades ("timestamp" DESC);

-- btc_trades.action='BUY'/'SELL' 필터 (HOLD 제외한 실제 매매만)
CREATE INDEX IF NOT EXISTS idx_btc_trades_action_ts
    ON public.btc_trades (action, "timestamp" DESC)
    WHERE action IN ('BUY','SELL');
