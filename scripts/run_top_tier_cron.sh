#!/bin/bash
# Top-tier phase job runner for cron (Phase 14~18).
#
# Usage:
#   scripts/run_top_tier_cron.sh phase14
#   scripts/run_top_tier_cron.sh phase15
#   scripts/run_top_tier_cron.sh phase16
#   scripts/run_top_tier_cron.sh phase18-alert
#   scripts/run_top_tier_cron.sh phase18-daily
#   scripts/run_top_tier_cron.sh phase18-weekly
#   scripts/run_top_tier_cron.sh all

set -u

OPENCLAW_JSON="/home/wlsdud5035/.openclaw/openclaw.json"
OPENCLAW_ENV="/home/wlsdud5035/.openclaw/.env"
WORKSPACE="/home/wlsdud5035/.openclaw/workspace"

cd "$WORKSPACE" || exit 1

if [ -f "$OPENCLAW_ENV" ]; then
  set -a
  source "$OPENCLAW_ENV"
  set +a
fi

ENV_VARS=$(.venv/bin/python3 -c "
import json, os
from shlex import quote
try:
    d = json.load(open('$OPENCLAW_JSON'))
except Exception:
    d = {}
for k, v in (d.get('env') or {}).items():
    if k != 'shellEnv' and isinstance(v, (str, int, float)) and not isinstance(v, bool):
        print(f'{k}={quote(str(v))}')
" 2>/dev/null)

while IFS= read -r line; do
  export "$line" 2>/dev/null
done <<< "$ENV_VARS"

MODE="${1:-all}"
KR_SYMBOL="${KR_SYMBOL:-005930}"
US_SYMBOL="${US_SYMBOL:-AAPL}"

run_py() {
  echo "[TOP_TIER] $(date -Iseconds) RUN: $*"
  .venv/bin/python3 "$@"
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "[TOP_TIER][WARN] failed rc=$rc cmd=$*" >&2
  fi
  return 0
}

run_phase14() {
  run_py btc/signals/orderflow.py --symbol BTCUSDT --seconds 15 --window 300 --large-threshold 10
  run_py btc/strategies/funding_carry.py --symbol BTCUSDT --notional 10000
  run_py btc/signals/arb_detector.py --alert 5 --reverse -1
  run_py btc/signals/whale_tracker.py
}

run_phase15() {
  run_py stocks/signals/orderbook_kr.py --symbol "$KR_SYMBOL"
  run_py stocks/signals/flow_kr.py --symbol "$KR_SYMBOL" --lookback 10
  run_py stocks/signals/dart_realtime.py --pages 1
  run_py stocks/strategies/sector_rotation.py --lookback 63
}

run_phase16() {
  run_py stocks/us_broker.py --symbol "$US_SYMBOL" --qty 1 --side buy --account
  run_py stocks/signals/options_flow.py --symbol "$US_SYMBOL"
  run_py stocks/signals/short_interest.py --symbol "$US_SYMBOL"

  if [ -n "${EARNINGS_ACTUAL_EPS:-}" ] && [ -n "${EARNINGS_CONSENSUS_EPS:-}" ]; then
    run_py stocks/signals/earnings_model.py --symbol "$US_SYMBOL" --actual "$EARNINGS_ACTUAL_EPS" --consensus "$EARNINGS_CONSENSUS_EPS" --std "${EARNINGS_SURPRISE_STD:-0.1}"
  fi

  if [ -n "${SEC13F_PREV_FILE:-}" ] && [ -n "${SEC13F_CURR_FILE:-}" ] && [ -n "${SEC13F_FUND:-}" ] && [ -f "$SEC13F_PREV_FILE" ] && [ -f "$SEC13F_CURR_FILE" ]; then
    run_py stocks/signals/sec_13f.py --fund "$SEC13F_FUND" --prev-file "$SEC13F_PREV_FILE" --curr-file "$SEC13F_CURR_FILE"
  fi
}

run_phase18_alert() {
  run_py agents/alert_manager.py \
    --drawdown "${ALERT_DRAWDOWN:-0}" \
    --var95 "${ALERT_VAR95:-0}" \
    --corr-shift "${ALERT_CORR_SHIFT:-0}" \
    --volume-spike "${ALERT_VOLUME_SPIKE:-1}"
}

run_phase18_daily() {
  run_py agents/daily_report.py
}

run_phase18_weekly() {
  run_py agents/weekly_report.py
}

case "$MODE" in
  phase14)
    run_phase14
    ;;
  phase15)
    run_phase15
    ;;
  phase16)
    run_phase16
    ;;
  phase18-alert)
    run_phase18_alert
    ;;
  phase18-daily)
    run_phase18_daily
    ;;
  phase18-weekly)
    run_phase18_weekly
    ;;
  all)
    run_phase14
    run_phase15
    run_phase16
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    echo "Valid modes: phase14, phase15, phase16, phase18-alert, phase18-daily, phase18-weekly, all" >&2
    exit 2
    ;;
esac

exit 0
