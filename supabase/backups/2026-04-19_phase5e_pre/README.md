# Pre-Phase5E DB 스냅샷 (2026-04-19)

Phase 5-E(DB 스키마 전면 정규화) 적용 직전의 Supabase public schema 전수 스냅샷.
롤백 근거용 — 정상 가동 확인 후 삭제 예정.

## 파일

| 파일 | 내용 |
|---|---|
| `01_columns.json` | 모든 public 테이블의 컬럼 목록 (information_schema) |
| `02_indexes.sql` | 모든 인덱스 정의 (pg_indexes → CREATE INDEX DDL) |
| `03_constraints.sql` | CHECK / UNIQUE / FK 제약 재현 SQL |
| `04_rls_policies.sql` | RLS 정책 (pg_policies) |
| `05_table_stats.md` | 테이블별 row 수·크기·RLS 요약 |

## 스냅샷 당시 상태
- Postgres 17.6.1.063 / Supabase 프로젝트 `tgbwciiwxggvvnwbhrkx` (my-openclaw)
- public schema 테이블 24개 (quant-agent 관련 23개 + `jay_users`)
- 전체 크기 ~137 MB
- quant-agent `publish-main` 브랜치 커밋 `9f0fd3b53` (Phase 5-D 완료 시점)

## 롤백 방법

스키마 변경 롤백은 Supabase 브랜치 merge 되돌리거나, 각 마이그레이션의 역 SQL
(`DROP COLUMN` / `ALTER COLUMN TYPE 원래타입` 등)을 직접 실행.

데이터 롤백은 **필요 없음**. Phase 5-E는 스키마 구조 변경만 수행하고
기존 row 데이터는 DROP/DELETE 하지 않음. 타입 변경(예: text → jsonb)은
`USING` 절로 안전 캐스팅.

## 삭제 시점
Phase 5-E merge 후 1주일(~2026-04-26)간 문제 없으면 `git rm -r` 후 커밋.
