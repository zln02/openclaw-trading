#!/usr/bin/env bash
# DRY_RUN 테스트 — 환경변수 안전 로딩
set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"

export DRY_RUN=1
exec .venv/bin/python btc/btc_trading_agent.py
