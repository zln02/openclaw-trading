-- Pre-Phase5E 인덱스 스냅샷 (2026-04-19)
-- public schema 전체 인덱스 정의. 롤백용 참고.

CREATE UNIQUE INDEX agent_decisions_pkey ON public.agent_decisions USING btree (id);
CREATE INDEX idx_agent_decisions_agent_market_created_at ON public.agent_decisions USING btree (agent_name, market, created_at DESC);
CREATE INDEX idx_agent_decisions_created_at ON public.agent_decisions USING btree (created_at DESC);
CREATE INDEX idx_agent_decisions_market_created_at ON public.agent_decisions USING btree (market, created_at DESC);

CREATE UNIQUE INDEX agent_performance_pkey ON public.agent_performance USING btree (id);
CREATE INDEX idx_agent_performance_agent_market_period_end ON public.agent_performance USING btree (agent_name, market, period_end DESC);
CREATE INDEX idx_agent_performance_created_at ON public.agent_performance USING btree (created_at DESC);
CREATE INDEX idx_agent_performance_period_end ON public.agent_performance USING btree (period_end DESC);
CREATE UNIQUE INDEX uq_agent_performance_period_agent_market ON public.agent_performance USING btree (period_end, agent_name, market);

CREATE UNIQUE INDEX btc_alt_data_pkey ON public.btc_alt_data USING btree (id);
CREATE INDEX idx_btc_alt_data_ts ON public.btc_alt_data USING btree ("timestamp" DESC);

CREATE UNIQUE INDEX btc_candles_pkey ON public.btc_candles USING btree (id);
CREATE INDEX idx_btc_candles_interval_timestamp ON public.btc_candles USING btree ("interval", "timestamp" DESC);
CREATE INDEX idx_btc_candles_timestamp ON public.btc_candles USING btree ("timestamp" DESC);
CREATE UNIQUE INDEX uq_btc_candles_ts_interval ON public.btc_candles USING btree ("timestamp", "interval");

CREATE UNIQUE INDEX btc_position_pkey ON public.btc_position USING btree (id);

CREATE UNIQUE INDEX btc_trades_pkey ON public.btc_trades USING btree (id);

CREATE UNIQUE INDEX circuit_breaker_events_pkey ON public.circuit_breaker_events USING btree (id);
CREATE INDEX idx_cb_events_created_at ON public.circuit_breaker_events USING btree (created_at DESC);
CREATE INDEX idx_cb_events_level ON public.circuit_breaker_events USING btree (trigger_level);

CREATE UNIQUE INDEX daily_ohlcv_pkey ON public.daily_ohlcv USING btree (stock_code, date);
CREATE INDEX idx_daily_ohlcv_code_date ON public.daily_ohlcv USING btree (stock_code, date DESC);

CREATE UNIQUE INDEX daily_reports_pkey ON public.daily_reports USING btree (report_id);
CREATE UNIQUE INDEX data_collection_log_pkey ON public.data_collection_log USING btree (log_id);
CREATE UNIQUE INDEX disclosures_pkey ON public.disclosures USING btree (stock_code, title);

CREATE UNIQUE INDEX drawdown_guard_state_pkey ON public.drawdown_guard_state USING btree (market);

CREATE UNIQUE INDEX execution_quality_pkey ON public.execution_quality USING btree (id);
CREATE INDEX idx_eq_market ON public.execution_quality USING btree (market);
CREATE INDEX idx_eq_symbol ON public.execution_quality USING btree (symbol);
CREATE INDEX idx_eq_timestamp ON public.execution_quality USING btree ("timestamp" DESC);

CREATE UNIQUE INDEX financial_statements_pkey ON public.financial_statements USING btree (stock_code);
CREATE UNIQUE INDEX financial_statements_stock_year_idx ON public.financial_statements USING btree (stock_code, fiscal_year);

CREATE UNIQUE INDEX health_snapshots_pkey ON public.health_snapshots USING btree (id);
CREATE INDEX idx_health_snapshots_component ON public.health_snapshots USING btree (component);
CREATE INDEX idx_health_snapshots_created_at ON public.health_snapshots USING btree (created_at DESC);

CREATE INDEX idx_intraday_code_interval_dt ON public.intraday_ohlcv USING btree (stock_code, time_interval, datetime DESC);
CREATE UNIQUE INDEX intraday_ohlcv_pkey ON public.intraday_ohlcv USING btree (id);
CREATE UNIQUE INDEX intraday_ohlcv_stock_code_datetime_time_interval_key ON public.intraday_ohlcv USING btree (stock_code, datetime, time_interval);

CREATE UNIQUE INDEX jay_users_email_key ON public.jay_users USING btree (email);
CREATE UNIQUE INDEX jay_users_pkey ON public.jay_users USING btree (id);

CREATE UNIQUE INDEX signal_ic_history_date_signal_key ON public.signal_ic_history USING btree (date, signal);
CREATE UNIQUE INDEX signal_ic_history_pkey ON public.signal_ic_history USING btree (id);

CREATE UNIQUE INDEX stock_ohlcv_pkey ON public.stock_ohlcv USING btree (id);
CREATE UNIQUE INDEX stock_ohlcv_ticker_date_key ON public.stock_ohlcv USING btree (ticker, date);

CREATE UNIQUE INDEX top50_stocks_pkey ON public.top50_stocks USING btree (stock_code);

CREATE INDEX idx_trade_executions_code_result ON public.trade_executions USING btree (stock_code, result);
CREATE INDEX idx_trade_executions_created ON public.trade_executions USING btree (created_at DESC);
CREATE UNIQUE INDEX trade_executions_pkey ON public.trade_executions USING btree (trade_id);

CREATE UNIQUE INDEX trade_snapshots_pkey ON public.trade_snapshots USING btree (snapshot_id);

CREATE INDEX idx_us_momentum_signals_run_date ON public.us_momentum_signals USING btree (run_date DESC);
CREATE INDEX idx_us_momentum_signals_symbol_date ON public.us_momentum_signals USING btree (symbol, run_date DESC);
CREATE UNIQUE INDEX us_momentum_signals_pkey ON public.us_momentum_signals USING btree (id);

CREATE INDEX idx_us_trade_executions_result ON public.us_trade_executions USING btree (result);
CREATE INDEX idx_us_trade_executions_symbol ON public.us_trade_executions USING btree (symbol, created_at DESC);
CREATE UNIQUE INDEX us_trade_executions_pkey ON public.us_trade_executions USING btree (id);
