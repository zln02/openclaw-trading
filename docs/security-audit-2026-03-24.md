# OpenClaw Security Audit — 2026-03-24

Automated audit performed by Claude Code (claude-sonnet-4-6).

---

## Summary

| Category | Status |
|----------|--------|
| Hardcoded secrets | ✅ CLEAN |
| Remote code execution | ✅ CLEAN |
| Bash sandbox (company/tools.py) | ✅ SECURE |
| shell=True usage | ✅ CLEAN |
| Test correctness (71 tests) | ⚠️ 1 FAIL |
| Lint (flake8) | ⚠️ 1 ERROR |
| Code convention (env_loader) | ⚠️ VIOLATIONS |

---

## Issues Found

### [HIGH] Test Bug — Wrong mock target
**File**: `tests/test_phase14_btc_top_tier.py:163`
**Function**: `test_execute_trade_returns_sell_order_failed_on_trailing_stop_error`

Expected `SELL_ORDER_FAILED`, got `TRAILING_STOP`.

**Root cause**: `_execute_sell_order` is a module-level function in `btc/btc_trading_agent.py`,
but the test patches it as an instance attribute via `patch.object(agent, "_execute_sell_order")`.
The mock is never called; the real function executes instead.

**Fix**:
```python
# Before (broken)
patch.object(agent, "_execute_sell_order", return_value=(False, "upbit_sell_error"))

# After (correct)
patch("btc.btc_trading_agent._execute_sell_order", return_value=(False, "upbit_sell_error"))
```

---

### [MEDIUM] F821 — Undefined name `RISK`
**File**: `btc/routes/btc_api.py:208`

```python
buy_threshold = RISK.get("buy_composite_min", 50) if "RISK" in dir() else 50
```

`RISK` is never defined in this file. `"RISK" in dir()` is always `False`, making
`RISK.get(...)` dead code. The variable is re-imported from `btc.btc_trading_agent`
on lines 210–212 anyway.

**Fix**: Remove the dead first line, or replace entirely with the try/except import below it.

---

### [LOW] Code Convention — Direct `os.getenv()` usage
**Rule**: All env vars must be loaded via `common/env_loader.load_env()` (CLAUDE.md rule 2).

Files bypassing `env_loader`:
- `secretary/core/autonomous_research.py` — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `BRAVE_API_KEY`
- `secretary/core/notion_skill.py` — `NOTION_TOKEN`, `NOTION_PAGE_ID`
- `secretary/core/agency_memory.py` — `AGENCY_MEMORY_DB`
- `agents/trading_agent_team.py` — `ANTHROPIC_API_KEY`
- `company/trading_company.py` — `ANTHROPIC_API_KEY`
- `stocks/kiwoom_client.py` — `TRADING_ENV`, `KIWOOM_REST_API_KEY`

---

## Checks Passed

- **Hardcoded secrets**: No API keys, tokens, or passwords found in source code.
- **Remote execution**: No `curl | sh`, `wget | sh`, or equivalent patterns.
- **Bash sandbox** (`company/tools.py`):
  - `shell=False` (uses `["bash", "--norc", "--noprofile", "-c", command]`)
  - Blocklist regex covers: `rm -rf`, `sudo`, `su`, `chmod /`, `chown root`, `dd if=`,
    `mkfs`, `shutdown/reboot`, `curl|sh`, `eval`, fork bomb, `kill -9 1`,
    `/etc/passwd|shadow|sudoers`, `iptables`, `base64 -d |`, `${IFS}`
  - `_safe_path()` enforces workspace confinement (path traversal blocked)
- **SQL injection**: Supabase client uses parameterized queries via SDK.
- **Auth**: All API routes protected via `Depends(_require_auth)` except `/health`.
- **Secrets storage**: Secrets in `.env` / `.docker-secrets/`, both in `.gitignore`.
- **Pre-commit hooks**: `detect-private-key`, `flake8`, `isort` configured.

---

## Test Results

```
71 tests collected
70 passed, 1 failed
```

Failure: `BtcTradingAgentSafetyTests::test_execute_trade_returns_sell_order_failed_on_trailing_stop_error`

---

## Tools Used

- `pytest --tb=short` (functional tests)
- `flake8 --max-line-length=120` (lint)
- Manual pattern scan: `subprocess`, `shell=True`, `eval`, `os.getenv`, hardcoded keys
