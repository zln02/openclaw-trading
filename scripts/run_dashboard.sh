#!/usr/bin/env bash
# 대시보드 실행 — 환경변수 안전 로딩
set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"
exec .venv/bin/python3 btc/btc_dashboard.py
