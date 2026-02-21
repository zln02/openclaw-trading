---
name: supabase-postgres-best-practices
description: Postgres performance optimization and best practices from Supabase. Use this skill when writing, reviewing, or optimizing Postgres queries, schema designs, or database configurations.
license: MIT
metadata:
  author: supabase
  version: "1.1.0"
  organization: Supabase
  date: January 2026
  abstract: Comprehensive Postgres performance optimization guide for developers using Supabase and Postgres. Contains performance rules across 8 categories, prioritized by impact from critical (query performance, connection management) to incremental (advanced features). Each rule includes detailed explanations, incorrect vs. correct SQL examples, query plan analysis, and specific performance metrics to guide automated optimization and code generation.
---

# Supabase Postgres Best Practices

Comprehensive performance optimization guide for Postgres, maintained by Supabase. Contains rules across 8 categories, prioritized by impact to guide automated query optimization and schema design.

## When to Apply

Reference these guidelines when:
- Writing SQL queries or designing schemas
- Implementing indexes or query optimization
- Reviewing database performance issues
- Configuring connection pooling or scaling
- Optimizing for Postgres-specific features
- Working with Row-Level Security (RLS)

## Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Query Performance | CRITICAL | `query-` |
| 2 | Connection Management | CRITICAL | `conn-` |
| 3 | Security & RLS | CRITICAL | `security-` |
| 4 | Schema Design | HIGH | `schema-` |
| 5 | Concurrency & Locking | MEDIUM-HIGH | `lock-` |
| 6 | Data Access Patterns | MEDIUM | `data-` |
| 7 | Monitoring & Diagnostics | LOW-MEDIUM | `monitor-` |
| 8 | Advanced Features | LOW | `advanced-` |

## How to Use

Read individual rule files for detailed explanations and SQL examples:

```
references/query-missing-indexes.md
references/schema-partial-indexes.md
references/_sections.md
```

Each rule file contains:
- Brief explanation of why it matters
- Incorrect SQL example with explanation
- Correct SQL example with explanation
- Optional EXPLAIN output or metrics
- Additional context and references
- Supabase-specific notes (when applicable)

## References

- https://www.postgresql.org/docs/current/
- https://supabase.com/docs
- https://wiki.postgresql.org/wiki/Performance_Optimization
- https://supabase.com/docs/guides/database/overview
- https://supabase.com/docs/guides/auth/row-level-security

## 테이블 생성 및 관리

Supabase 데이터베이스에 테이블을 생성할 때는 `exec` 도구를 사용하여 `psql` 명령어를 실행합니다.

### ⚠️ 중요: 환경변수 사용 필수

**절대 하드코딩된 연결 문자열을 사용하지 마세요!** 반드시 `$SUPABASE_DB_URL` 환경변수를 사용해야 합니다.

❌ **잘못된 방법** (사용 금지):
```bash
# 플레이스홀더나 하드코딩된 연결 문자열 사용 금지
psql "postgresql://postgres.tgbwciiwxggvvnwbhrkx:[YOUR-PASSWORD]@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
psql "postgresql://postgres.tgbwciiwxggvvnwbhrkx:[YOUR-LATEST-PASSWORD]@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
psql "postgresql://postgres.tgbwciiwxggvvnwbhrkx:비밀번호@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
```

✅ **올바른 방법** (반드시 사용):
```bash
# 환경변수 사용 (필수)
psql "$SUPABASE_DB_URL" -c "CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);"
```

### 환경변수

`SUPABASE_DB_URL` 환경변수가 이미 설정되어 있습니다. 이는 `openclaw.json`의 `env` 블록에 설정되어 있으며, exec 도구에서 자동으로 사용할 수 있습니다.

### 테이블 생성 예시

```bash
# 기본 테이블 생성 (환경변수 사용)
psql "$SUPABASE_DB_URL" -c "CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);"

# 테이블 목록 확인
psql "$SUPABASE_DB_URL" -c "\dt"

# 테이블 구조 확인
psql "$SUPABASE_DB_URL" -c "\d 테이블명"
```

### exec 도구 사용 시

exec 도구를 사용할 때는 다음과 같이 환경변수를 명시적으로 전달할 수 있습니다:

```javascript
exec({
  command: psql
