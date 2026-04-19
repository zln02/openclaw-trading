-- Phase 5-E Step 2: factor_snapshot 컬럼을 text → jsonb로 변환
-- 목적: factor 쿼리 가능화, 타입 안전성. btc_trades.indicator_snapshot은 이미 jsonb.
-- 안전 변환: 빈 문자열/공백은 NULL로, 잘못된 JSON은 실패(사전 검증 필수)

-- 사전 검증 쿼리 (마이그레이션 실행 전 수동 확인용. 여기선 주석으로만)
--
-- SELECT trade_id, factor_snapshot FROM public.trade_executions
-- WHERE factor_snapshot IS NOT NULL AND TRIM(factor_snapshot) <> ''
--   AND NOT (factor_snapshot::text ~ '^[\s]*[{\[]');
--
-- 위 쿼리가 row를 반환하면 해당 row의 factor_snapshot을 수동 정리 후 재시도.

-- 1. trade_executions.factor_snapshot
ALTER TABLE public.trade_executions
    ALTER COLUMN factor_snapshot TYPE jsonb
    USING (
        CASE
            WHEN factor_snapshot IS NULL OR TRIM(factor_snapshot) = '' THEN NULL
            ELSE factor_snapshot::jsonb
        END
    );

COMMENT ON COLUMN public.trade_executions.factor_snapshot IS
    '체결 시점 팩터 스냅샷(JSON). attribution 계산에 사용. 2026-04-19 text → jsonb 전환.';

-- 2. us_trade_executions.factor_snapshot
ALTER TABLE public.us_trade_executions
    ALTER COLUMN factor_snapshot TYPE jsonb
    USING (
        CASE
            WHEN factor_snapshot IS NULL OR TRIM(factor_snapshot) = '' THEN NULL
            ELSE factor_snapshot::jsonb
        END
    );

COMMENT ON COLUMN public.us_trade_executions.factor_snapshot IS
    '체결 시점 팩터 스냅샷(JSON). 2026-04-19 text → jsonb 전환.';
