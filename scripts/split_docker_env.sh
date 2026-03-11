#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_ENV="${1:-$ROOT_DIR/.env}"
RUNTIME_ENV="$ROOT_DIR/.env.runtime"
SECRETS_DIR="$ROOT_DIR/.docker-secrets"
OPENCLAW_JSON="${OPENCLAW_CONFIG_PATH:-${OPENCLAW_CONFIG_DIR:-$HOME/.openclaw}/openclaw.json}"

if [ ! -f "$SOURCE_ENV" ]; then
  echo "source env not found: $SOURCE_ENV" >&2
  exit 1
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR" 2>/dev/null || true

SECRET_KEYS=(
  ANTHROPIC_API_KEY
  DASHBOARD_PASSWORD
  KIWOOM_MOCK_REST_API_APP_KEY
  KIWOOM_MOCK_REST_API_SECRET_KEY
  OPENCLAW_GATEWAY_TOKEN
  SUPABASE_SECRET_KEY
  SUPABASE_URL
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  UPBIT_ACCESS_KEY
  UPBIT_SECRET_KEY
)

lookup_secret_value() {
  local key="$1"
  python3 - "$SOURCE_ENV" "$OPENCLAW_JSON" "$key" <<'PY'
import json
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
json_path = Path(sys.argv[2]).expanduser()
target = sys.argv[3]

value = ""
if env_path.exists():
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, val = line.partition("=")
        if key.strip() == target:
            value = val.strip().strip("\"'")
            break

if not value and json_path.exists():
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    env = data.get("env") or {}
    raw = env.get(target)
    if isinstance(raw, str) and raw:
        value = raw
    elif target == "TELEGRAM_BOT_TOKEN":
        tg = ((data.get("channels") or {}).get("telegram") or {}).get("botToken")
        if isinstance(tg, str) and tg:
            value = tg

sys.stdout.write(value)
PY
}

for key in "${SECRET_KEYS[@]}"; do
  value="$(lookup_secret_value "$key")"
  if [ -n "$value" ]; then
    umask 077
    printf '%s' "$value" > "$SECRETS_DIR/$key"
  else
    rm -f "$SECRETS_DIR/$key"
  fi
done

awk '
  BEGIN {
    secret["DASHBOARD_PASSWORD"]=1
    secret["KIWOOM_MOCK_REST_API_APP_KEY"]=1
    secret["KIWOOM_MOCK_REST_API_SECRET_KEY"]=1
    secret["OPENCLAW_GATEWAY_TOKEN"]=1
    secret["SUPABASE_URL"]=1
    secret["SUPABASE_SECRET_KEY"]=1
    secret["ANTHROPIC_API_KEY"]=1
    secret["TELEGRAM_BOT_TOKEN"]=1
    secret["TELEGRAM_CHAT_ID"]=1
    secret["UPBIT_ACCESS_KEY"]=1
    secret["UPBIT_SECRET_KEY"]=1
  }
  /^[[:space:]]*#/ || /^[[:space:]]*$/ { print; next }
  {
    split($0, parts, "=")
    key=parts[1]
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
    if (!(key in secret)) print
  }
' "$SOURCE_ENV" > "$RUNTIME_ENV"

chmod 600 "$RUNTIME_ENV" 2>/dev/null || true
echo "generated $RUNTIME_ENV and $SECRETS_DIR"
