-- Phase 5-E Step 1: signal_source 컬럼 추가
-- 목적: 룰/ML/LLM/composite 신호 소스를 모든 체결 테이블에 기록 → 소스별 성과 측정 가능화
-- 비파괴: 기존 컬럼 유지. us_trade_executions.source는 다음 마이그레이션에서 정리.

-- 1. trade_executions (KR)
ALTER TABLE public.trade_executions
    ADD COLUMN IF NOT EXISTS signal_source text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_trade_executions_signal_source'
    ) THEN
        ALTER TABLE public.trade_executions
            ADD CONSTRAINT chk_trade_executions_signal_source
            CHECK (signal_source IS NULL OR signal_source IN ('rule','ml','llm','composite','manual'));
    END IF;
END $$;

COMMENT ON COLUMN public.trade_executions.signal_source IS
    '매매 신호의 결정 소스 — rule(순수 룰) / ml(모델) / llm(analyze_with_ai) / composite(룰+ML 블렌드) / manual(수동). NULL은 legacy row (Phase 5-E 이전).';

-- 2. us_trade_executions — 기존 source 컬럼 데이터를 signal_source로 복사
ALTER TABLE public.us_trade_executions
    ADD COLUMN IF NOT EXISTS signal_source text;

-- 빈 문자열("")은 NULL로 변환, 그 외는 그대로 매핑
UPDATE public.us_trade_executions
SET signal_source = NULLIF(NULLIF(source, ''), ' ')
WHERE signal_source IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_us_trade_executions_signal_source'
    ) THEN
        ALTER TABLE public.us_trade_executions
            ADD CONSTRAINT chk_us_trade_executions_signal_source
            CHECK (signal_source IS NULL OR signal_source IN ('rule','ml','llm','composite','manual','ai_premarket'));
    END IF;
END $$;

COMMENT ON COLUMN public.us_trade_executions.signal_source IS
    '매매 신호 소스 — rule / ml / llm / composite / manual / ai_premarket (장전 AI 전략). 과거 source 컬럼에서 백필됨. source 컬럼은 다음 단계에서 DROP 예정.';

-- 3. btc_trades — action(BUY/SELL/HOLD)과 별개로 signal_source 추가
ALTER TABLE public.btc_trades
    ADD COLUMN IF NOT EXISTS signal_source text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_btc_trades_signal_source'
    ) THEN
        ALTER TABLE public.btc_trades
            ADD CONSTRAINT chk_btc_trades_signal_source
            CHECK (signal_source IS NULL OR signal_source IN ('rule','ml','llm','composite','manual'));
    END IF;
END $$;

COMMENT ON COLUMN public.btc_trades.signal_source IS
    '매매 신호 소스 — rule / ml / llm / composite / manual. action=HOLD row도 어떤 로직이 HOLD를 결정했는지 구분용으로 채워질 수 있음.';

-- 4. 인덱스: signal_source 필터가 들어가는 분석 쿼리 가속
CREATE INDEX IF NOT EXISTS idx_trade_executions_source_created
    ON public.trade_executions (signal_source, created_at DESC)
    WHERE signal_source IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_us_trade_executions_source_created
    ON public.us_trade_executions (signal_source, created_at DESC)
    WHERE signal_source IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_btc_trades_source_ts
    ON public.btc_trades (signal_source, "timestamp" DESC)
    WHERE signal_source IS NOT NULL;
