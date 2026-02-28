"""Shared paths and constants for the OpenClaw trading system."""
from pathlib import Path

OPENCLAW_ROOT = Path("/home/wlsdud5035/.openclaw")
WORKSPACE = OPENCLAW_ROOT / "workspace"
LOG_DIR = OPENCLAW_ROOT / "logs"

BRAIN_PATH = WORKSPACE / "brain"
MEMORY_PATH = WORKSPACE / "memory"

BTC_LOG = LOG_DIR / "btc_trading.log"
STOCK_TRADING_LOG = LOG_DIR / "stock_trading.log"
STOCK_CHECK_LOG = LOG_DIR / "stock_check.log"
STOCK_PREMARKET_LOG = LOG_DIR / "stock_premarket.log"
STOCK_COLLECTOR_LOG = LOG_DIR / "stock_collector.log"
US_TRADING_LOG = LOG_DIR / "us_trading.log"
DASHBOARD_LOG = LOG_DIR / "dashboard.log"

STRATEGY_JSON = WORKSPACE / "stocks" / "today_strategy.json"
OPENCLAW_JSON = OPENCLAW_ROOT / "openclaw.json"

DASHBOARD_PORT = 8080

# ── 기본 리스크 파라미터 (에이전트별 override 가능) ──────────────────
# 실제 파라미터는 각 에이전트 파일의 RISK 딕셔너리가 우선 적용됨.
# 공통 default로만 사용.

BTC_RISK_DEFAULTS: dict = {
    "split_ratios":       [0.15, 0.25, 0.40],
    "split_rsi":          [55, 45, 35],
    "invest_ratio":        0.30,
    "stop_loss":          -0.03,
    "take_profit":         0.12,
    "partial_tp_pct":      0.08,
    "partial_tp_ratio":    0.50,
    "trailing_stop":       0.02,
    "trailing_activate":   0.015,
    "trailing_adaptive":   True,
    "max_daily_loss":     -0.08,
    "max_drawdown":       -0.15,
    "min_confidence":      65,
    "max_trades_per_day":  3,
    "fee_buy":             0.001,
    "fee_sell":            0.001,
    "buy_composite_min":   45,
    "sell_composite_max":  20,
    "timecut_days":        7,
    "cooldown_minutes":    30,
    "volatility_filter":   True,
    "funding_filter":      True,
    "oi_filter":           True,
    "kimchi_premium_max":  5.0,
    "dynamic_weights":     True,
    # 레짐별 복합 스코어 보너스/페널티 (calc_btc_composite 내부 적용)
    "regime_bonus": {
        "RISK_ON":    +5,
        "TRANSITION":  0,
        "RISK_OFF":  -10,
        "CRISIS":    -20,
    },
}

KR_RISK_DEFAULTS: dict = {
    "invest_ratio":        0.25,
    "stop_loss":          -0.025,
    "take_profit":         0.08,
    "partial_tp_pct":      0.05,
    "partial_tp_ratio":    0.50,
    "trailing_stop":       0.02,
    "trailing_activate":   0.015,
    "trailing_adaptive":   True,
    "max_daily_loss":     -0.05,
    "max_drawdown":       -0.12,
    "min_confidence":      65,
    "min_score":           65,
    "max_positions":       5,
    "max_sector_positions": 2,
    "volatility_sizing":   True,
    "fee":                 0.0015,
}

US_RISK_DEFAULTS: dict = {
    "invest_ratio":        0.20,
    "stop_loss":          -0.035,
    "take_profit":         0.10,
    "partial_tp_pct":      0.06,
    "partial_tp_ratio":    0.50,
    "trailing_stop":       0.02,
    "trailing_activate":   0.02,
    "trailing_adaptive":   True,
    "max_daily_loss":     -0.05,
    "max_drawdown":       -0.12,
    "min_confidence":      60,
    "min_score":           50,
    "max_positions":       5,
    "max_sector_positions": 2,
    "vix_max":             35,
    "earnings_buffer_days": 5,
    "volatility_sizing":   True,
    "fee":                 0.0,   # Alpaca zero commission
}

# 신호 IC 최소 임계값 (이 이하면 신호 비활성 권고)
SIGNAL_IC_MIN: float = 0.02
SIGNAL_IC_IR_MIN: float = 0.3
