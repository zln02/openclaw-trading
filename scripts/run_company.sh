#!/bin/bash
# OpenClaw AI Company 실행 래퍼
# 사용법:
#   ./scripts/run_company.sh --task "대시보드 버그 수정해줘"
#   ./scripts/run_company.sh --task "QA 검사 해줘" --role qa
#   ./scripts/run_company.sh --list-roles

OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"

cd "$WORKSPACE" || exit 1

if [ -f "$OPENCLAW_ENV" ]; then set -a; source "$OPENCLAW_ENV"; set +a; fi

ENV_VARS=$(.venv/bin/python3 -c "
import json, os
from shlex import quote
d = json.load(open('$OPENCLAW_JSON'))
for k, v in d.get('env', {}).items():
    if k != 'shellEnv' and isinstance(v, (str, int, float)) and not isinstance(v, bool):
        print(f'{k}={quote(str(v))}')
if not os.environ.get('ANTHROPIC_API_KEY'):
    key = d.get('env', {}).get('ANTHROPIC_API_KEY') or ''
    if key:
        print('ANTHROPIC_API_KEY=' + quote(str(key)))
" 2>/dev/null)

while IFS= read -r line; do
    export "$line" 2>/dev/null
done <<< "$ENV_VARS"

echo "[COMPANY] $(date -Iseconds) ARGS=$@"
exec .venv/bin/python3 -m company "$@"
