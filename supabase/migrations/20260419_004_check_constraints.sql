-- Phase 5-E Step 4: CHECK 제약 보강 (enum 자리의 free-text 방지)
-- 기존 값을 확인 후 호환되는 범위로 설정 (2026-04-19 실제 분포 기준).
-- 모두 NULL 허용 유지 (legacy row·default row 보호).

-- trade_type: 체결 유형 (BUY/SELL)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_trade_executions_trade_type') THEN
        ALTER TABLE public.trade_executions
            ADD CONSTRAINT chk_trade_executions_trade_type
            CHECK (trade_type IS NULL OR trade_type IN ('BUY','SELL'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_us_trade_executions_trade_type') THEN
        ALTER TABLE public.us_trade_executions
            ADD CONSTRAINT chk_us_trade_executions_trade_type
            CHECK (trade_type IS NULL OR trade_type IN ('BUY','SELL'));
    END IF;
END $$;

-- btc_trades.action: BUY/SELL/HOLD (SKIP 기록은 없지만 호환 위해 포함)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_btc_trades_action') THEN
        ALTER TABLE public.btc_trades
            ADD CONSTRAINT chk_btc_trades_action
            CHECK (action IS NULL OR action IN ('BUY','SELL','HOLD','SKIP'));
    END IF;
END $$;

-- trade_executions.result: CLOSED / CLOSED_SYNC / SYNC_ERROR / OPEN / STOPPED
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_trade_executions_result') THEN
        ALTER TABLE public.trade_executions
            ADD CONSTRAINT chk_trade_executions_result
            CHECK (result IS NULL OR result IN ('OPEN','CLOSED','STOPPED','CLOSED_SYNC','SYNC_ERROR'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_us_trade_executions_result') THEN
        ALTER TABLE public.us_trade_executions
            ADD CONSTRAINT chk_us_trade_executions_result
            CHECK (result IS NULL OR result IN ('OPEN','CLOSED','STOPPED','CLOSED_SYNC','SYNC_ERROR'));
    END IF;
END $$;

-- btc_position.status: OPEN / CLOSED
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_btc_position_status') THEN
        ALTER TABLE public.btc_position
            ADD CONSTRAINT chk_btc_position_status
            CHECK (status IS NULL OR status IN ('OPEN','CLOSED'));
    END IF;
END $$;

-- btc_candles.interval: minute5 / minute10 / minute15 / minute30 / minute60 / hour1 / day / week / month
-- 실제 쓰이는 값만 포함 (btc_dashboard에서 받는 intervals)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_btc_candles_interval') THEN
        ALTER TABLE public.btc_candles
            ADD CONSTRAINT chk_btc_candles_interval
            CHECK ("interval" IN ('minute5','minute10','minute15','minute30','minute60','hour1','day','week','month'));
    END IF;
END $$;

-- drawdown_guard_state.market: btc/kr/us
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_drawdown_guard_market') THEN
        ALTER TABLE public.drawdown_guard_state
            ADD CONSTRAINT chk_drawdown_guard_market
            CHECK (market IN ('btc','kr','us'));
    END IF;
END $$;

-- execution_quality.side: BUY/SELL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_execution_quality_side') THEN
        ALTER TABLE public.execution_quality
            ADD CONSTRAINT chk_execution_quality_side
            CHECK (side IN ('BUY','SELL'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_execution_quality_market') THEN
        ALTER TABLE public.execution_quality
            ADD CONSTRAINT chk_execution_quality_market
            CHECK (market IN ('btc','kr','us','auto'));
    END IF;
END $$;
