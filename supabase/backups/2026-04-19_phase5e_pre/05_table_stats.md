# Pre-Phase5E 테이블 통계 (2026-04-19)

| 테이블 | 추정 Row | 전체 크기 | 테이블 크기 | RLS |
|---|---:|---:|---:|:---:|
| health_snapshots | 289,892 | 74 MB | 52 MB | ❌ |
| intraday_ohlcv | 135,640 | 39 MB | 15 MB | ❌ |
| btc_trades | 41,429 | 17 MB | 16 MB | ❌ |
| daily_ohlcv | 13,979 | 3672 kB | 1888 kB | ❌ |
| btc_candles | 2,839 | 816 kB | 288 kB | ✅ |
| circuit_breaker_events | 2,340 | 808 kB | 536 kB | ❌ |
| us_momentum_signals | 1,428 | 480 kB | 152 kB | ❌ |
| financial_statements | 50 | 104 kB | 32 kB | ❌ |
| trade_executions | 38 | 96 kB | 16 kB | ❌ |
| us_trade_executions | 37 | 96 kB | 16 kB | ❌ |
| drawdown_guard_state | 1 | 64 kB | 8192 B | ✅ |
| stock_ohlcv | 20 | 48 kB | 8192 B | ❌ |
| agent_performance | 0 | 48 kB | 0 B | ✅ |
| btc_alt_data | 51 | 48 kB | 8192 B | ✅ |
| signal_ic_history | — | 48 kB | 8192 B | ❌ |
| execution_quality | 0 | 40 kB | 0 B | ❌ |
| agent_decisions | 0 | 40 kB | 0 B | ✅ |
| btc_position | 24 | 32 kB | 8192 B | ❌ |
| disclosures | — | 32 kB | 8192 B | ❌ |
| daily_reports | — | 32 kB | 8192 B | ❌ |
| top50_stocks | 53 | 24 kB | 8192 B | ❌ |
| trade_snapshots | 0 | 16 kB | 0 B | ❌ |
| data_collection_log | 0 | 16 kB | 0 B | ❌ |
| jay_users | 0 | 24 kB | 0 B | ✅ |

**전체 DB 크기 (public)**: ~137 MB (대부분 health_snapshots + intraday_ohlcv + btc_trades)

**관찰**:
- `health_snapshots` 52 MB는 고주파 로깅. retention/파티셔닝 검토 필요.
- `intraday_ohlcv` 15 MB는 정상 (백테스트용).
- `execution_quality` 테이블은 정의됐으나 0 row — 코드 통합 미완.
- `trade_snapshots` 0 row — FK만 있고 미사용.
- `data_collection_log` 0 row — 미사용.
- `disclosures` 3 row, `daily_reports` 36 row — 저조한 활용.

**RLS 활성 6개**: agent_decisions · agent_performance · btc_alt_data · btc_candles · drawdown_guard_state · jay_users
**RLS 비활성 18개**: 나머지. 일관성 정리 대상.
