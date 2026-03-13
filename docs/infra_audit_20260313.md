# Infrastructure Audit 2026-03-13

## Summary

- Root filesystem usage: `95%` (`/dev/sda1 49G / 45G used / 2.7G free`)
- OpenClaw logs size: `63M`
- Root-level `node_modules`: `1.9G`
- Memory: `7.8Gi total`, `2.9Gi free`, `664Mi swap used`

## Findings

- Duplicate supervisors were active for BTC agent.
  - Docker service: `openclaw-btc-agent-1`
  - User cron: `run_btc_cron.sh`
- Duplicate supervisors were active for Telegram bot.
  - Docker service: `openclaw-telegram-bot-1`
  - User cron `@reboot` + watchdog entry
- This duplication was the main reason CPU investigation showed overlapping agent processes.

## Actions Taken

- Backed up current crontab to [crontab_backup_20260313.txt](/home/wlsdud5035/openclaw/docs/crontab_backup_20260313.txt)
- Removed cron entries that duplicated Docker-managed services:
  - `run_btc_cron.sh`
  - `stocks/telegram_bot.py` `@reboot`
  - `telegram_bot.py` watchdog entry
- Installed log rotation policy at `/etc/logrotate.d/openclaw`
- Validated logrotate config with `logrotate -d /etc/logrotate.d/openclaw`

## Current Service Ownership

- Dashboard: Docker
- BTC agent: Docker
- US agent: Docker
- Telegram bot: Docker
- KR agent: cron/workspace
- Top-tier signal collectors: cron/workspace

## Residual Risks

- Disk pressure remains high because `/` is still at `95%`
- `~/openclaw/node_modules/` is still `1.9G` and likely a cleanup target later
- Some signal jobs return fallback/`NO_DATA` when network data is unavailable, but they no longer fail due to wrapper or logger issues
