"""기술적 지표 계산 — ta 라이브러리 기반 통합 모듈."""
from __future__ import annotations

import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from typing import Any, Dict, Optional


def calc_rsi(closes: pd.Series, period: int = 14) -> float:
    """RSI 계산. closes가 Series일 때 ta 라이브러리 사용."""
    if closes is None or len(closes) < period + 1:
        return 50.0
    rsi_series = RSIIndicator(close=closes, window=period).rsi()
    val = rsi_series.iloc[-1]
    return round(float(val), 1) if pd.notna(val) else 50.0


def calc_bb(closes: pd.Series, window: int = 20, std: float = 2.0) -> Dict[str, float]:
    """볼린저 밴드 상/하단 + 현재 위치(%)."""
    bb = BollingerBands(close=closes, window=window, window_dev=std)
    upper = float(bb.bollinger_hband().iloc[-1])
    lower = float(bb.bollinger_lband().iloc[-1])
    price = float(closes.iloc[-1])
    width = upper - lower if upper != lower else 1.0
    position = round((price - lower) / width * 100, 1)
    return {"upper": round(upper, 2), "lower": round(lower, 2), "position": position}


def calc_ema(closes: pd.Series, period: int = 20) -> float:
    """EMA 계산."""
    ema = EMAIndicator(close=closes, window=period).ema_indicator()
    val = ema.iloc[-1]
    return round(float(val), 2) if pd.notna(val) else float(closes.iloc[-1])


def calc_macd(closes: pd.Series) -> Dict[str, float]:
    """MACD (diff, signal, histogram)."""
    macd = MACD(close=closes, window_slow=26, window_fast=12, window_sign=9)
    return {
        "macd": round(float(macd.macd().iloc[-1] or 0), 2),
        "signal": round(float(macd.macd_signal().iloc[-1] or 0), 2),
        "diff": round(float(macd.macd_diff().iloc[-1] or 0), 2),
    }


def calc_volume_ratio(volumes: pd.Series, period: int = 20) -> float:
    """현재 거래량 / 20일 평균 거래량."""
    if volumes is None or len(volumes) < period:
        return 1.0
    avg = volumes.rolling(period).mean().iloc[-1]
    if avg <= 0:
        return 1.0
    return round(float(volumes.iloc[-1] / avg), 2)


def full_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """OHLCV DataFrame에서 전체 지표 스냅샷 반환."""
    if df is None or df.empty or len(df) < 50:
        return {}
    close = df["close"] if "close" in df.columns else df["Close"]
    volume = df["volume"] if "volume" in df.columns else df.get("Volume", pd.Series())

    result: Dict[str, Any] = {
        "price": float(close.iloc[-1]),
        "rsi": calc_rsi(close),
        "ema20": calc_ema(close, 20),
        "ema50": calc_ema(close, 50),
    }
    result.update({"macd_" + k: v for k, v in calc_macd(close).items()})

    bb = calc_bb(close)
    result["bb_upper"] = bb["upper"]
    result["bb_lower"] = bb["lower"]
    result["bb_position"] = bb["position"]

    if volume is not None and len(volume) > 0:
        result["volume"] = float(volume.iloc[-1])
        result["vol_ratio"] = calc_volume_ratio(volume)

    return result
