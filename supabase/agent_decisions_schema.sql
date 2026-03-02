-- Trading Agent Team — 에이전트 의사결정 기록 테이블
-- Supabase SQL 에디터에서 실행하세요.

CREATE TABLE IF NOT EXISTS agent_decisions (
    id          BIGSERIAL PRIMARY KEY,
    market      TEXT        NOT NULL,           -- 'btc' | 'kr' | 'us'
    decision    TEXT        NOT NULL,           -- 'BUY' | 'SELL' | 'HOLD'
    reasoning   TEXT,                           -- 결정 근거
    confidence  NUMERIC(5,2),                  -- 0~100
    action      TEXT        DEFAULT 'pending',  -- 'executed' | 'skipped' | 'pending'
    agent_team  TEXT        DEFAULT 'claude_5agent',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 시장별 최근 결정 조회 인덱스
CREATE INDEX IF NOT EXISTS idx_agent_decisions_market_created
    ON agent_decisions (market, created_at DESC);

-- RLS: 서비스 롤만 허용 (anon 차단)
ALTER TABLE agent_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_only" ON agent_decisions
    FOR ALL
    USING (auth.role() = 'service_role');
