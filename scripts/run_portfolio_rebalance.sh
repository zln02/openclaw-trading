#!/usr/bin/env bash
# 매주 일요일 23:45 crontab으로 실행 (param_optimizer 직후)
set -euo pipefail

cd /home/wlsdud5035/.openclaw/workspace

python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

from common.equity_loader import load_all_positions
from quant.portfolio.optimizer import PortfolioOptimizer

positions = load_all_positions()
expected_returns = {}
asset_class_map = {}
covariance = {}

for pos in positions:
    symbol = str(pos.get("symbol") or "").upper()
    if not symbol:
        continue
    market_value = float(pos.get("market_value") or 0.0)
    base_score = 0.08
    expected_returns[symbol] = max(base_score, min(0.20, 0.05 + (market_value / 10_000_000.0)))
    asset_class_map[symbol] = str(pos.get("asset_class") or pos.get("market") or "OTHER").upper()
    covariance[symbol] = {symbol: 0.04 if asset_class_map[symbol] != "CRYPTO" else 0.16}

result = PortfolioOptimizer().optimize(
    expected_returns=expected_returns,
    covariance=covariance,
    asset_class_map=asset_class_map,
    method="risk_parity",
)

out_path = Path("brain/portfolio/target_weights.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(out_path)
PY
