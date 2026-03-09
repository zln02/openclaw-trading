#!/usr/bin/env bash
# OpenClaw AI Company 실행 래퍼
# 사용법:
#   ./scripts/run_company.sh --task "대시보드 버그 수정해줘"
#   ./scripts/run_company.sh --task "QA 검사 해줘" --role qa
#   ./scripts/run_company.sh --list-roles

set -euo pipefail

source "$(dirname "$0")/load_env.sh"
load_openclaw_env
require_openclaw_workspace

cd "$WORKSPACE"

echo "[COMPANY] $(date -Iseconds) ARGS=$@"
exec .venv/bin/python3 -m company "$@"
