-- Pre-Phase5E CHECK / UNIQUE / FK 제약 스냅샷 (2026-04-19)
-- contype c=CHECK, u=UNIQUE, f=FOREIGN KEY

-- agent_decisions
ALTER TABLE public.agent_decisions ADD CONSTRAINT chk_agent_decisions_confidence
    CHECK (((confidence IS NULL) OR ((confidence >= (0.0)::double precision) AND (confidence <= (100.0)::double precision))));
ALTER TABLE public.agent_decisions ADD CONSTRAINT chk_agent_decisions_market
    CHECK ((market = ANY (ARRAY['btc'::text, 'kr'::text, 'us'::text])));

-- agent_performance
ALTER TABLE public.agent_performance ADD CONSTRAINT chk_agent_performance_market
    CHECK ((market = ANY (ARRAY['btc'::text, 'kr'::text, 'us'::text])));
ALTER TABLE public.agent_performance ADD CONSTRAINT uq_agent_performance_period_agent_market
    UNIQUE (period_end, agent_name, market);

-- btc_candles
ALTER TABLE public.btc_candles ADD CONSTRAINT uq_btc_candles_ts_interval
    UNIQUE ("timestamp", "interval");

-- intraday_ohlcv
ALTER TABLE public.intraday_ohlcv ADD CONSTRAINT intraday_ohlcv_stock_code_datetime_time_interval_key
    UNIQUE (stock_code, datetime, time_interval);

-- jay_users
ALTER TABLE public.jay_users ADD CONSTRAINT jay_users_email_key UNIQUE (email);

-- signal_ic_history
ALTER TABLE public.signal_ic_history ADD CONSTRAINT signal_ic_history_date_signal_key
    UNIQUE (date, signal);

-- stock_ohlcv
ALTER TABLE public.stock_ohlcv ADD CONSTRAINT stock_ohlcv_ticker_date_key
    UNIQUE (ticker, date);

-- trade_snapshots
ALTER TABLE public.trade_snapshots ADD CONSTRAINT trade_snapshots_trade_id_fkey
    FOREIGN KEY (trade_id) REFERENCES trade_executions(trade_id);
