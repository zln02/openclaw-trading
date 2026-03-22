#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <interval-seconds> <python-script> [args...]" >&2
  exit 2
fi

INTERVAL="$1"
shift

PYTHON_BIN="${PYTHON_BIN:-python}"
if [ -x "/app/.venv/bin/python" ]; then
  PYTHON_BIN="/app/.venv/bin/python"
elif [ -x "/app/.venv/bin/python3" ]; then
  PYTHON_BIN="/app/.venv/bin/python3"
fi

echo "[AGENT_LOOP] start interval=${INTERVAL}s cmd=$*"

while true; do
  start_ts="$(date +%s)"
  echo "[AGENT_LOOP] $(date -Iseconds) run: $*"

  set +e
  "$PYTHON_BIN" "$@"
  rc=$?
  set -e

  end_ts="$(date +%s)"
  elapsed=$((end_ts - start_ts))
  sleep_for=$((INTERVAL - elapsed))

  if [ "$rc" -ne 0 ]; then
    echo "[AGENT_LOOP] $(date -Iseconds) rc=${rc} elapsed=${elapsed}s"
    if [ "$sleep_for" -lt 30 ]; then
      sleep_for=30
    fi
  elif [ "$sleep_for" -lt 1 ]; then
    sleep_for=1
  fi

  echo "[AGENT_LOOP] $(date -Iseconds) sleep=${sleep_for}s"
  sleep "$sleep_for"
done
