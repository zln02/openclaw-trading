# btc_indicators.py — 기술적 지표 계산 (경량, 200캔들만 사용)
# ta 라이브러리 사용 (pandas-ta는 Python 3.12+ 필요)
from __future__ import annotations

import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from typing import Any


def calculate_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """OHLCV DataFrame에서 지표 계산 후 최신 봉 한 개 스냅샷 반환."""
    if df is None or df.empty or len(df) < 50:
        return {}
    d = df.copy()
    close = d["close"]
    d["ema20"] = EMAIndicator(close=close, window=20).ema_indicator()
    d["ema50"] = EMAIndicator(close=close, window=50).ema_indicator()
    d["rsi"] = RSIIndicator(close=close, window=14).rsi()
    macd = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    d["macd"] = macd.macd()
    d["signal"] = macd.macd_signal()
    bb = BollingerBands(close=close, window=20, window_dev=2.0)
    d["bb_upper"] = bb.bollinger_hband()
    d["bb_lower"] = bb.bollinger_lband()
    latest = d.iloc[-1]
    out = {
        "price": float(latest["close"]),
        "ema20": round(float(latest.get("ema20", 0) or 0), 0),
        "ema50": round(float(latest.get("ema50", 0) or 0), 0),
        "rsi": round(float(latest.get("rsi", 50) or 50), 1),
        "macd": round(float(latest.get("macd", 0) or 0), 0),
        "macd_sig": round(float(latest.get("signal", 0) or 0), 0),
        "volume": round(float(latest.get("volume", 0) or 0), 4),
    }
    if pd.notna(latest.get("bb_upper")):
        out["bb_upper"] = round(float(latest["bb_upper"]), 0)
    if pd.notna(latest.get("bb_lower")):
        out["bb_lower"] = round(float(latest["bb_lower"]), 0)
    return out
