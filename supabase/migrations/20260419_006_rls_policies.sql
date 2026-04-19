-- Phase 5-E Step 6: RLS 일괄 활성화 + service_role 정책
-- 현재 RLS off 18개 테이블을 모두 ENABLE → service_role 외 접근 차단
-- (quant-agent는 SUPABASE_KEY로 service_role 사용 → 영향 없음)
-- (jay_users는 제외 — quant-agent 범위 밖)

-- 1. RLS Enable (공용 헬퍼 없이 DO 블록으로 멱등성 보장)
DO $$
DECLARE
    tbl text;
    tables text[] := ARRAY[
        'daily_ohlcv','top50_stocks','disclosures','financial_statements',
        'trade_executions','trade_snapshots','data_collection_log',
        'daily_reports','stock_ohlcv','btc_trades','btc_position',
        'intraday_ohlcv','us_momentum_signals','us_trade_executions',
        'signal_ic_history','circuit_breaker_events','execution_quality',
        'health_snapshots'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
    END LOOP;
END $$;

-- 2. service_role 전용 ALL 정책 추가 (없을 때만)
DO $$
DECLARE
    tbl text;
    policy_name text;
    tables text[] := ARRAY[
        'daily_ohlcv','top50_stocks','disclosures','financial_statements',
        'trade_executions','trade_snapshots','data_collection_log',
        'daily_reports','stock_ohlcv','btc_trades','btc_position',
        'intraday_ohlcv','us_momentum_signals','us_trade_executions',
        'signal_ic_history','circuit_breaker_events','execution_quality',
        'health_snapshots'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        policy_name := 'service_role_all_' || tbl;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public' AND tablename = tbl AND policyname = policy_name
        ) THEN
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)',
                policy_name, tbl
            );
        END IF;
    END LOOP;
END $$;
