#!/usr/bin/env bash
# BTC 자산 equity 스냅샷을 호스트에서 직접 기록 (Docker 컨테이너 read-only 우회)
# cron: */10 * * * * /home/wlsdud5035/quant-agent/scripts/record_btc_equity.sh
set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env

PYTHON_BIN="${WORKSPACE}/.venv/bin/python3"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

"$PYTHON_BIN" - <<'PY'
import sys, json, os
from pathlib import Path

sys.path.insert(0, os.environ.get("OPENCLAW_WORKSPACE_DIR",
    str(Path.home() / ".openclaw" / "workspace")))

from common.env_loader import load_env
load_env()

try:
    import pyupbit
    from common.equity_loader import append_equity_snapshot

    access = os.environ.get("UPBIT_ACCESS_KEY", "")
    secret = os.environ.get("UPBIT_SECRET_KEY", "")
    if not access or not secret:
        print("UPBIT keys 없음 — skip")
        sys.exit(0)

    upbit = pyupbit.Upbit(access, secret)
    krw = float(upbit.get_balance("KRW") or 0)
    btc = float(upbit.get_balance("BTC") or 0)
    price = float(pyupbit.get_current_price("KRW-BTC") or 0)
    equity = krw + btc * price
    if equity > 0:
        append_equity_snapshot("btc", equity, {"source": "upbit_balances", "price": price})
        print(f"BTC equity 기록: {equity:,.0f} KRW (BTC={btc:.6f}, price={price:,.0f})")
    else:
        print("equity 0 — skip")
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PY
