-- Phase 5-E Step 3: timestamp 컬럼 통일 (timestamp → timestamptz)
-- 목적: 타임존 정보 유지. 전체 DB 관례(timestamptz)에 맞춤.
-- 가정: 기존 timestamp 값이 UTC로 저장됐다고 간주 (AT TIME ZONE 'UTC' 캐스팅).
-- btc_trading_agent/stock_trading_agent 등은 모두 datetime.now(KST) 또는 now() 사용 →
-- timestamptz로 INSERT 시 Postgres가 자동으로 UTC 변환 저장 → 변환 안전.

-- 1. data_collection_log.timestamp (rows=0, 안전)
ALTER TABLE public.data_collection_log
    ALTER COLUMN "timestamp" TYPE timestamp with time zone
    USING "timestamp" AT TIME ZONE 'UTC';

ALTER TABLE public.data_collection_log
    ALTER COLUMN "timestamp" SET DEFAULT now();

COMMENT ON COLUMN public.data_collection_log."timestamp" IS
    '로그 생성 시각. 2026-04-19 timestamp → timestamptz 전환 (기존 row는 UTC 가정 캐스팅, row=0).';

-- 2. trade_snapshots.timestamp (rows=0, 안전)
ALTER TABLE public.trade_snapshots
    ALTER COLUMN "timestamp" TYPE timestamp with time zone
    USING "timestamp" AT TIME ZONE 'UTC';

COMMENT ON COLUMN public.trade_snapshots."timestamp" IS
    '스냅샷 시각. 2026-04-19 timestamp → timestamptz 전환 (rows=0).';
