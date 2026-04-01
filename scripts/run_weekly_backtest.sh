#!/bin/bash
set -euo pipefail

cd /home/wlsdud5035/quant-agent
source .venv/bin/activate

python backtest/backtest_engine.py --days 90 2>&1
