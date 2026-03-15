-- Supabase: daily_reports.content JSONB column
-- Supabase Dashboard > SQL Editor에서 실행

ALTER TABLE daily_reports
    ADD COLUMN IF NOT EXISTS content JSONB;
