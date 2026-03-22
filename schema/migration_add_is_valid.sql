-- Migration: add is_valid column to execution_quality
-- 실행 방법: Supabase Dashboard > SQL Editor에 붙여넣기 후 실행
-- 생성일: 2026-03-21

ALTER TABLE execution_quality
ADD COLUMN IF NOT EXISTS is_valid BOOLEAN DEFAULT TRUE;
