# Repo Consolidation Audit — 2026-03-13

## Goal

Unify executable code under `/home/wlsdud5035/openclaw` while keeping runtime state and secrets under `/home/wlsdud5035/.openclaw`.

## Result

- Cron entrypoints now point to `/home/wlsdud5035/openclaw/scripts/*`.
- Docker-managed services remain in `/home/wlsdud5035/openclaw`.
- Runtime state remains under `/home/wlsdud5035/.openclaw`.
- `/home/wlsdud5035/.openclaw/workspace` is no longer the intended execution repo. It remains as a state/archive area during burn-in.

## Runtime Ownership

- Docker:
  - dashboard
  - btc agent
  - us agent
  - telegram bot
- Cron:
  - KR trading
  - top-tier signal phases
  - health checks
  - research and reporting jobs

## Key Changes

1. Copied cron-owned code paths from `~/.openclaw/workspace` into `~/openclaw`.
2. Switched active user crontab paths from `~/.openclaw/workspace` to `~/openclaw`.
3. Updated `scripts/load_env.sh` so:
   - code executes from `~/openclaw`
   - logs load from `~/.openclaw/logs`
   - state loads from `~/.openclaw/workspace/brain`
   - memory loads from `~/.openclaw/workspace/memory`
   - strategy JSON loads from `~/.openclaw/workspace/stocks/today_strategy.json`
4. Updated `common/config.py` to support separate code and state paths.
5. Fixed `agents/alert_manager.py` to accept `--snapshot-file`.
6. Fixed `scripts/run_top_tier_cron.sh` to pass the actual configured brain path.

## Verification

- `scripts/run_stock_cron.sh status` runs from `~/openclaw`.
- `scripts/run_us_cron.sh status` runs from `~/openclaw`.
- `scripts/run_top_tier_cron.sh phase15` runs from `~/openclaw`.
- `scripts/run_top_tier_cron.sh phase18-alert` now reads the generated risk snapshot and completes successfully.
- Active crontab references `/home/wlsdud5035/openclaw`.

## Remaining Burn-in Notes

- Keep `~/.openclaw/workspace` in place for now because state files still live there.
- Old backup files remain in the repo tree but are intentionally not part of the consolidation commit.
- After burn-in, the next cleanup step is to migrate state paths out of `~/.openclaw/workspace` into first-class `~/.openclaw/{brain,memory,...}` directories.
