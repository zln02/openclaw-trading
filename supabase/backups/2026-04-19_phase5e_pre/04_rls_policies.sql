-- Pre-Phase5E RLS 정책 스냅샷 (2026-04-19)
-- service_role만 허용하는 PERMISSIVE ALL 정책. 일부는 roles=service_role, 일부는 roles=public + qual 체크.

-- agent_decisions
CREATE POLICY service_role_only_agent_decisions ON public.agent_decisions
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- agent_performance
CREATE POLICY service_role_only_agent_performance ON public.agent_performance
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- btc_alt_data
CREATE POLICY service_role_only_btc_alt_data ON public.btc_alt_data
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- btc_candles
CREATE POLICY service_role_only_btc_candles ON public.btc_candles
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- drawdown_guard_state
CREATE POLICY service_role_full_access ON public.drawdown_guard_state
    FOR ALL TO public USING (auth.role() = 'service_role'::text) WITH CHECK (auth.role() = 'service_role'::text);

-- jay_users (quant-agent 무관 — 참고용)
CREATE POLICY service_role_all ON public.jay_users
    FOR ALL TO public USING (auth.role() = 'service_role'::text) WITH CHECK (auth.role() = 'service_role'::text);

-- RLS 활성화된 테이블: agent_decisions, agent_performance, btc_alt_data, btc_candles, drawdown_guard_state, jay_users
-- RLS 비활성화 테이블 (통과): daily_ohlcv, top50_stocks, disclosures, financial_statements, trade_executions, trade_snapshots, data_collection_log, daily_reports, stock_ohlcv, btc_trades, btc_position, intraday_ohlcv, us_momentum_signals, us_trade_executions, signal_ic_history, circuit_breaker_events, execution_quality, health_snapshots
