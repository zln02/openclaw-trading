#!/bin/bash
set -euo pipefail

cd /home/wlsdud5035/openclaw
source .venv/bin/activate

python backtest/backtest_engine.py --days 90 2>&1
