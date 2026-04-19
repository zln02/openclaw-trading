# Supabase Migrations — Phase 5-E (2026-04-19)

DB 스키마 전면 정규화. 각 파일은 **멱등(idempotent)** 하게 작성되어 재실행 안전.
Supabase 브랜치(`create_branch`)에 순서대로 적용한 뒤 스모크 테스트 통과 시 main으로 merge.

## 순서

| 순 | 파일 | 목적 | 파괴적? |
|---|---|---|:---:|
| 1 | `20260419_001_add_signal_source.sql` | trade_executions/us_trade_executions/btc_trades에 signal_source 컬럼 + CHECK + 인덱스 | ❌ |
| 2 | `20260419_002_factor_snapshot_jsonb.sql` | factor_snapshot text → jsonb (trade_executions/us_trade_executions) | ⚠️ 타입 변경 |
| 3 | `20260419_003_timezone_unify.sql` | data_collection_log/trade_snapshots timestamp → timestamptz (둘 다 row=0) | ❌ |
| 4 | `20260419_004_check_constraints.sql` | trade_type/result/action/status/interval/market CHECK | ❌ |
| 5 | `20260419_005_partial_indexes.sql` | 부분 인덱스 (status='OPEN' 등) | ❌ |
| 6 | `20260419_006_rls_policies.sql` | RLS 일괄 enable + service_role ALL 정책 (18개 테이블) | ⚠️ 권한 |
| 7 | `20260419_007_table_comments.sql` | COMMENT ON TABLE/COLUMN 문서화 | ❌ |

## 설계 근거
→ `supabase/SCHEMA_DESIGN.md`

## 롤백
각 마이그레이션은 역변환 가능:
- signal_source ADD → `ALTER TABLE ... DROP COLUMN signal_source CASCADE`
- factor_snapshot jsonb → `ALTER COLUMN factor_snapshot TYPE text USING factor_snapshot::text`
- timezone → `ALTER COLUMN "timestamp" TYPE timestamp USING "timestamp" AT TIME ZONE 'UTC'`
- CHECK → `ALTER TABLE ... DROP CONSTRAINT ...`
- RLS → `ALTER TABLE ... DISABLE ROW LEVEL SECURITY; DROP POLICY ...`

롤백용 snapshot: `supabase/backups/2026-04-19_phase5e_pre/` 참조.

## 적용 방법
Supabase MCP:
1. `create_branch` — 임시 브랜치 (copy-on-write)
2. `apply_migration` × 7 — 위 순서대로
3. 스모크 테스트 (SELECT 1, INSERT, UPDATE 등)
4. `merge_branch` — 통과 시 prod 반영
5. `delete_branch` — 브랜치 정리
