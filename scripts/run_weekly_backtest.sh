#!/bin/bash
set -euo pipefail

cd /home/wlsdud5035/quant-agent
PYTHON_BIN="/home/wlsdud5035/quant-agent/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python runtime not found: $PYTHON_BIN" >&2
    exit 1
fi

"$PYTHON_BIN" backtest/backtest_engine.py --days 90 2>&1
