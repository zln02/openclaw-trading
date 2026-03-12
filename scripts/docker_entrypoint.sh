#!/usr/bin/env bash
set -euo pipefail

load_secret_env() {
  local env_name="$1"
  local secret_name="${2:-$1}"
  local secret_path=""

  if [ -f "/run/local-secrets/${secret_name}" ]; then
    secret_path="/run/local-secrets/${secret_name}"
  elif [ -f "/run/secrets/${secret_name}" ]; then
    secret_path="/run/secrets/${secret_name}"
  fi

  if [ -n "$secret_path" ]; then
    export "${env_name}=$(tr -d '\r' < "$secret_path")"
  fi
}

load_secret_env "DASHBOARD_PASSWORD"
load_secret_env "KIWOOM_MOCK_REST_API_APP_KEY"
load_secret_env "KIWOOM_MOCK_REST_API_SECRET_KEY"
load_secret_env "OPENCLAW_GATEWAY_TOKEN"
load_secret_env "SUPABASE_URL"
load_secret_env "SUPABASE_SECRET_KEY"
load_secret_env "OPENAI_API_KEY"
load_secret_env "ANTHROPIC_API_KEY"
load_secret_env "TELEGRAM_BOT_TOKEN"
load_secret_env "TELEGRAM_CHAT_ID"
load_secret_env "UPBIT_ACCESS_KEY"
load_secret_env "UPBIT_SECRET_KEY"

exec "$@"
