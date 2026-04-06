#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="/home/wlsdud5035/.openclaw/workspace/"
TARGET_DIR="/home/wlsdud5035/openclaw/"

MODE="--dry-run"
if [[ "${1:-}" == "--apply" ]]; then
  MODE=""
fi

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "target repo not found: $TARGET_DIR"
  exit 1
fi

echo "Sync source: $SOURCE_DIR"
echo "Sync target: $TARGET_DIR"
if [[ -n "$MODE" ]]; then
  echo "Mode: dry-run"
else
  echo "Mode: apply"
fi

EXCLUDES=(
  "./.env"
  "./openclaw.json"
  "./.venv"
  "./brain"
  "./logs"
  "./dashboard/node_modules"
  "./mobile/node_modules"
  "./mobile/.expo"
  "./catboost_info"
)

if command -v rsync >/dev/null 2>&1; then
  rsync -av ${MODE} \
    --exclude='.env' \
    --exclude='secretary/.env' \
    --exclude='skills/**/.env' \
    --exclude='openclaw.json' \
    --exclude='.venv/' \
    --exclude='secretary/.venv/' \
    --exclude='brain/' \
    --exclude='logs/' \
    --exclude='dashboard/node_modules/' \
    --exclude='dashboard/dist/' \
    --exclude='mobile/node_modules/' \
    --exclude='mobile/.expo/' \
    --exclude='catboost_info/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.db' \
    --exclude='*.sqlite3' \
    "$SOURCE_DIR" "$TARGET_DIR"
  exit 0
fi

echo "rsync not found; using tar fallback"

if [[ -n "$MODE" ]]; then
  (
    cd "$SOURCE_DIR"
    find . \
      -path './.env' -prune -o \
      -path './secretary/.env' -prune -o \
      -path './openclaw.json' -prune -o \
      -path './.venv' -prune -o \
      -path './secretary/.venv' -prune -o \
      -path './brain' -prune -o \
      -path './logs' -prune -o \
      -path './dashboard/node_modules' -prune -o \
      -path './dashboard/dist' -prune -o \
      -path './mobile/node_modules' -prune -o \
      -path './mobile/.expo' -prune -o \
      -path './catboost_info' -prune -o \
      -path '*/__pycache__' -prune -o \
      -name '*.pyc' -prune -o \
      -name '*.db' -prune -o \
      -name '*.sqlite3' -prune -o \
      -type f -print
  )
  exit 0
fi

(
  cd "$SOURCE_DIR"
  tar -cf - \
    --exclude='.env' \
    --exclude='secretary/.env' \
    --exclude='skills/**/.env' \
    --exclude='openclaw.json' \
    --exclude='.venv' \
    --exclude='secretary/.venv' \
    --exclude='brain' \
    --exclude='logs' \
    --exclude='dashboard/node_modules' \
    --exclude='dashboard/dist' \
    --exclude='mobile/node_modules' \
    --exclude='mobile/.expo' \
    --exclude='catboost_info' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.db' \
    --exclude='*.sqlite3' \
    .
) | (
  cd "$TARGET_DIR"
  tar -xf -
)
