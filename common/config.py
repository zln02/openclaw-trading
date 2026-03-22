"""Shared paths and constants for the OpenClaw trading system."""
from __future__ import annotations

import os
from pathlib import Path


def _resolve_openclaw_root() -> Path:
    root = (
        os.environ.get("OPENCLAW_CONFIG_DIR")
        or os.environ.get("OPENCLAW_STATE_DIR")
        or str(Path.home() / ".openclaw")
    )
    return Path(root).expanduser()


OPENCLAW_ROOT = _resolve_openclaw_root()
WORKSPACE = Path(
    os.environ.get("OPENCLAW_WORKSPACE_DIR", str(OPENCLAW_ROOT / "workspace"))
).expanduser()
LOG_DIR = Path(os.environ.get("OPENCLAW_LOG_DIR", str(OPENCLAW_ROOT / "logs"))).expanduser()

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
OPENCLAW_JSON = Path(
    os.environ.get("OPENCLAW_CONFIG_PATH", str(OPENCLAW_ROOT / "openclaw.json"))
).expanduser()

DASHBOARD_PORT = 8080

# ── 기본 리스크 파라미터 (에이전트별 override 가능) ──────────────────
# 실제 파라미터는 각 에이전트 파일의 RISK 딕셔너리가 우선 적용됨.
# 공통 default로만 사용.

BTC_RISK_DEFAULTS: dict = {
    "split_ratios":       [0.15, 0.25, 0.40],
    "split_rsi":          [55, 45, 35],
    "invest_ratio":        0.30,
    "stop_loss":          -0.03,
    "take_profit":         0.08,
    "partial_tp_pct":      0.03,
    "partial_tp_ratio":    0.50,
    "trailing_stop":       0.02,
    "trailing_activate":   0.015,
    "trailing_adaptive":   True,
    "max_daily_loss":     -0.08,
    "max_drawdown":       -0.15,
    "min_confidence":      65,
    "max_trades_per_day":  2,
    "fee_buy":             0.001,
    "fee_sell":            0.001,
    "buy_composite_min":   50,
    "sell_composite_max":  20,
    "timecut_days":        7,
    "cooldown_minutes":    60,
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
    "max_sector_weight":   0.30,           # v6.1: 단일 섹터 최대 30% 비중
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
    "max_sector_weight":   0.30,           # v6.1: 단일 섹터 최대 30% 비중
    "vix_max":             35,
    "earnings_buffer_days": 5,
    "volatility_sizing":   True,
    "fee":                 0.0,   # Alpaca zero commission
    "max_hold_days":       20,    # v6: 좀비 포지션 하드 컷오프
    "indicator_fail_max":  3,     # v6: 지표 N회 연속 실패 시 강제 매도
}

# ── ATR 기반 동적 손절/익절 (v6) ──────────────────────────────
ATR_SL_MULTIPLIER: float = 1.5      # SL = 1.5× ATR
ATR_TP_MULTIPLIER: float = 3.0      # TP = 3.0× ATR (2:1 reward-risk)
ATR_MIN_STOP_LOSS: float = -0.02    # 바닥 (최소 -2%)
ATR_MAX_STOP_LOSS: float = -0.08    # 천장 (최대 -8%)
ATR_MIN_TAKE_PROFIT: float = 0.06   # 최소 +6%
ATR_MAX_TAKE_PROFIT: float = 0.25   # 최대 +25%

# ── 레짐별 리스크 오버라이드 (v6) ──────────────────────────────
REGIME_RISK_OVERRIDES: dict = {
    "RISK_ON":    {"max_positions": 5, "sl_mult": 1.0, "allow_new_buys": True},
    "TRANSITION": {"max_positions": 4, "sl_mult": 1.0, "allow_new_buys": True},
    "RISK_OFF":   {"max_positions": 3, "sl_mult": 0.8, "allow_new_buys": True},
    "CRISIS":     {"max_positions": 1, "sl_mult": 0.6, "allow_new_buys": False},
}

# ── 뉴스 감정 게이트 (v6) ──────────────────────────────────────
NEWS_SENTIMENT_BLOCK_THRESHOLD: float = -0.5   # 이 이하 → BUY 차단
NEWS_SENTIMENT_BONUS_THRESHOLD: float = 0.3    # 이 이상 → composite +5
NEWS_SENTIMENT_BONUS_POINTS: int = 5

# ── ETF 섹터 매핑 (yfinance에서 sector 미반환하는 ETF용) ────────
ETF_SECTOR_MAP: dict = {
    "XLE": "Energy", "XLF": "Financial Services", "XLK": "Technology",
    "XLV": "Healthcare", "XLI": "Industrials", "XLP": "Consumer Defensive",
    "XLY": "Consumer Cyclical", "XLU": "Utilities", "XLB": "Basic Materials",
    "XLRE": "Real Estate", "XLC": "Communication Services",
    "SPY": "Index", "QQQ": "Index", "IWM": "Index", "DIA": "Index",
    "GLD": "Commodities", "SLV": "Commodities", "USO": "Energy",
    "TLT": "Bonds", "HYG": "Bonds",
}

# 신호 IC 최소 임계값 (이 이하면 신호 비활성 권고)
SIGNAL_IC_MIN: float = 0.015       # v6.1: 0.02 → 0.015 (초기 부트스트랩 허용)
SIGNAL_IC_IR_MIN: float = 0.2      # v6.1: 0.3 → 0.2 (데이터 부족기 완화)
SIGNAL_IC_MIN_SAMPLES: int = 3     # v6.1: 최소 데이터 건수 (기존 5 → 3)
MAX_PORTFOLIO_VAR: float = 0.03  # v6: 5% → 3% 타이트한 리스크
MIN_ARB_PROFIT_USD: float = 50.0
MAX_GAS_GWEI: float = 30.0
MAX_ARB_SLIPPAGE_BPS: float = 30.0

# ── Alpha Researcher 파라미터 공간 (None이면 alpha_researcher.py 내 기본값 사용) ──
ALPHA_PARAM_SPACE: dict | None = {
    "rsi_window":        [7, 14, 21],
    "momentum_lookback": [5, 10, 20],
    "bb_window":         [15, 20, 30],
    "atr_multiplier":    [1.5, 2.0, 2.5],
}

# ── Param Optimizer 자율 조정 임계값 ──────────────────────────────────────────
PARAM_OPT_WIN_RATE_LOW: float = 0.40    # 승률 이 이하 → 방어 모드
PARAM_OPT_SHARPE_HIGH: float = 1.5     # 샤프 이 이상 → 공격 허용
PARAM_OPT_IR_IMPROVE_MIN: float = 0.10 # IR 개선 최소값 (+10% 이상일 때 파라미터 교체)

# ── Attribution 다운웨이팅 임계값 ────────────────────────────────────────────
ATTRIBUTION_DOWNWEIGHT_THRESHOLD: float = -0.5  # avg_contrib 이 이하 → 다운웨이팅
ATTRIBUTION_DECAY_FACTOR: float = 0.5           # 다운웨이팅 계수 (weight × 이 값)
