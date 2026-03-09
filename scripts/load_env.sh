#!/usr/bin/env bash
# OpenClaw 공통 환경변수 로더. 각 cron 스크립트에서 source로 포함.
#
# 사용법:
#   source "$(dirname "$0")/load_env.sh"
#   load_openclaw_env

set -u

OPENCLAW_ROOT="${OPENCLAW_CONFIG_DIR:-${OPENCLAW_STATE_DIR:-$HOME/.openclaw}}"
OPENCLAW_ROOT="${OPENCLAW_ROOT/#\~/$HOME}"
OPENCLAW_JSON="${OPENCLAW_CONFIG_PATH:-$OPENCLAW_ROOT/openclaw.json}"
OPENCLAW_ENV="$OPENCLAW_ROOT/.env"
WORKSPACE="${OPENCLAW_WORKSPACE_DIR:-$OPENCLAW_ROOT/workspace}"
WORKSPACE="${WORKSPACE/#\~/$HOME}"
LOG_DIR="${OPENCLAW_LOG_DIR:-$OPENCLAW_ROOT/logs}"
LOG_DIR="${LOG_DIR/#\~/$HOME}"

emit_openclaw_env_pairs() {
    python3 - "$OPENCLAW_JSON" "$OPENCLAW_ENV" "$WORKSPACE" <<'PY'
import json
import re
import sys
from pathlib import Path

openclaw_json = Path(sys.argv[1])
env_files = [
    Path(sys.argv[2]),
    Path(sys.argv[3]) / ".env",
    Path(sys.argv[3]) / "skills" / "kiwoom-api" / ".env",
]
key_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
loaded = {}


def emit(key: str, value: str) -> None:
    sys.stdout.write(key)
    sys.stdout.write("\0")
    sys.stdout.write(value)
    sys.stdout.write("\0")


if openclaw_json.exists():
    try:
        data = json.loads(openclaw_json.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    for key, value in (data.get("env") or {}).items():
        if key != "shellEnv" and key_re.match(str(key)) and isinstance(value, (str, int, float)) and not isinstance(value, bool):
            loaded.setdefault(str(key), str(value))
    telegram = ((data.get("channels") or {}).get("telegram") or {}).get("botToken")
    if isinstance(telegram, str) and telegram:
        loaded.setdefault("TELEGRAM_BOT_TOKEN", telegram)

for path in env_files:
    if not path.exists():
        continue
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        continue
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key_re.match(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        hash_index = value.find(" #")
        if hash_index != -1:
            value = value[:hash_index].rstrip()
        loaded.setdefault(key, value.replace("\\n", "\n"))

for key, value in loaded.items():
    emit(key, value)
PY
}

load_openclaw_env() {
    export OPENCLAW_ROOT OPENCLAW_JSON OPENCLAW_ENV WORKSPACE LOG_DIR
    while IFS= read -r -d '' key && IFS= read -r -d '' value; do
        export "$key=$value"
    done < <(emit_openclaw_env_pairs)
}

require_openclaw_workspace() {
    if [ ! -d "$WORKSPACE" ]; then
        echo "OpenClaw workspace not found: $WORKSPACE" >&2
        return 1
    fi
}
