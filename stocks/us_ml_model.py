#!/usr/bin/env python3
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.config import BRAIN_PATH
from stocks.ml_model import (
    _build_catboost_model,
    _build_lgbm_model,
    _build_model,
    _fit_model,
)
from us_momentum_backtest import US_UNIVERSE


MODEL_DIR = BRAIN_PATH / "ml" / "us"
XGB_PATH = MODEL_DIR / "xgb_model.ubj"
LGBM_PATH = MODEL_DIR / "lgbm_model.txt"
CAT_PATH = MODEL_DIR / "catboost_model.cbm"
META_PATH = MODEL_DIR / "meta_model.pkl"
META_JSON_PATH = MODEL_DIR / "ensemble_meta.json"

TARGET_DAYS = 5
TARGET_RETURN = 0.03
BUY_THRESHOLD = 0.65

FEATURE_NAMES = [
    "rsi_14",
    "bb_pos",
    "vol_ratio_5_20",
    "return_1d",
    "return_5d",
    "return_20d",
    "return_60d",
    "close_vs_ma20",
    "close_vs_ma60",
    "volatility_20d",
    "atr_pct_14",
    "near_high_60d",
    "sector_etf_momentum",
    "spy_beta_60d",
    "earnings_revision",
    "options_iv_rank",
    "forward_pe",
    "profit_margin",
    "roe",
    "market_regime",
]

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financial": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Utilities": "XLU",
}

DEFAULT_SYMBOLS = [
    sym for sym in US_UNIVERSE
    if sym not in {"SPY", "QQQ", "XLK", "XLF", "XLE", "XLV"}
]

_INFO_CACHE: dict[str, dict] = {}
_HIST_CACHE: dict[tuple[str, str], pd.DataFrame] = {}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, (list, tuple)) and not value:
            return default
        return float(value)
    except Exception:
        return default


def _download_history(symbol: str, period: str = "5y") -> pd.DataFrame:
    key = (symbol, period)
    if key in _HIST_CACHE:
        return _HIST_CACHE[key].copy()
    hist = yf.Ticker(symbol).history(period=period, auto_adjust=False)
    if hist is None or hist.empty:
        hist = pd.DataFrame()
    _HIST_CACHE[key] = hist.copy()
    return hist.copy()


def _info(symbol: str) -> dict:
    if symbol not in _INFO_CACHE:
        try:
            _INFO_CACHE[symbol] = yf.Ticker(symbol).info or {}
        except Exception:
            _INFO_CACHE[symbol] = {}
    return _INFO_CACHE[symbol]


def _sector_etf(symbol: str, info: dict | None = None) -> str:
    info = info or _info(symbol)
    sector = info.get("sector") or info.get("industryDisp") or ""
    return SECTOR_ETF_MAP.get(str(sector), "SPY")


def _build_feature_frame(symbol: str, period: str = "5y") -> pd.DataFrame:
    info = _info(symbol)
    hist = _download_history(symbol, period=period)
    if hist.empty or len(hist) < 260:
        return pd.DataFrame()

    spy = _download_history("SPY", period=period)
    if spy.empty or len(spy) < 260:
        return pd.DataFrame()

    sector_symbol = _sector_etf(symbol, info=info)
    sector = _download_history(sector_symbol, period=period)
    if sector.empty:
        sector = spy.copy()

    df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
    df = df.rename(columns=str.lower)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"].replace(0, np.nan)

    rsi = RSIIndicator(close=close, window=14).rsi()
    bb = BollingerBands(close=close, window=20, window_dev=2)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    bb_width = (bb_upper - bb_lower).replace(0, np.nan)
    bb_pos = ((close - bb_lower) / bb_width * 100.0).clip(lower=0, upper=100)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_pct = (tr.rolling(14).mean() / close.replace(0, np.nan)) * 100.0

    ret_1d = close.pct_change(1) * 100.0
    ret_5d = close.pct_change(5) * 100.0
    ret_20d = close.pct_change(20) * 100.0
    ret_60d = close.pct_change(60) * 100.0
    vol_ratio = volume.rolling(5).mean() / volume.rolling(20).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    close_vs_ma20 = (close / ma20 - 1.0) * 100.0
    close_vs_ma60 = (close / ma60 - 1.0) * 100.0
    vol_20d = close.pct_change().rolling(20).std() * np.sqrt(252) * 100.0
    near_high = (close / high.rolling(60).max()) * 100.0

    spy_close = spy["Close"].reindex(df.index).ffill()
    spy_ret_daily = spy_close.pct_change()
    stock_ret_daily = close.pct_change()
    beta = (
        stock_ret_daily.rolling(60).cov(spy_ret_daily)
        / spy_ret_daily.rolling(60).var().replace(0, np.nan)
    )
    spy_ma200 = spy_close.rolling(200).mean()
    regime = np.where(spy_close > spy_ma200, 1.0, -1.0)

    sector_close = sector["Close"].reindex(df.index).ffill()
    sector_momentum = ((close / close.shift(20)) - (sector_close / sector_close.shift(20))) * 100.0

    earnings_revision = _safe_float(
        info.get("earningsQuarterlyGrowth", info.get("earningsGrowth", 0.0))
    ) * 100.0
    iv_rank = min(max(_safe_float(info.get("impliedVolatility", 0.0)) * 100.0, 0.0), 100.0)
    forward_pe = _safe_float(info.get("forwardPE", info.get("trailingPE", 0.0)))
    profit_margin = _safe_float(info.get("profitMargins", 0.0)) * 100.0
    roe = _safe_float(info.get("returnOnEquity", 0.0)) * 100.0

    frame = pd.DataFrame(
        {
            "rsi_14": rsi,
            "bb_pos": bb_pos,
            "vol_ratio_5_20": vol_ratio.replace([np.inf, -np.inf], np.nan),
            "return_1d": ret_1d,
            "return_5d": ret_5d,
            "return_20d": ret_20d,
            "return_60d": ret_60d,
            "close_vs_ma20": close_vs_ma20,
            "close_vs_ma60": close_vs_ma60,
            "volatility_20d": vol_20d,
            "atr_pct_14": atr_pct,
            "near_high_60d": near_high,
            "sector_etf_momentum": sector_momentum,
            "spy_beta_60d": beta,
            "earnings_revision": earnings_revision,
            "options_iv_rank": iv_rank,
            "forward_pe": forward_pe,
            "profit_margin": profit_margin,
            "roe": roe,
            "market_regime": regime,
        },
        index=df.index,
    )
    frame["symbol"] = symbol
    frame["future_return_5d"] = close.shift(-TARGET_DAYS) / close - 1.0
    frame["label"] = (frame["future_return_5d"] >= TARGET_RETURN).astype(int)
    frame = frame.dropna(subset=FEATURE_NAMES + ["future_return_5d"]).copy()
    return frame


def load_training_data(symbols: list[str] | None = None, period: str = "5y") -> tuple[np.ndarray | None, np.ndarray | None, pd.DataFrame | None]:
    symbols = symbols or DEFAULT_SYMBOLS
    frames = []
    for symbol in symbols:
        try:
            frame = _build_feature_frame(symbol, period=period)
        except Exception:
            continue
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return None, None, None

    data = pd.concat(frames).sort_index()
    X = data[FEATURE_NAMES].astype(float).to_numpy()
    y = data["label"].astype(int).to_numpy()
    return X, y, data


def _predict_proba(model, X: np.ndarray) -> np.ndarray:
    if model is None:
        return np.zeros(len(X))
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    pred = model.predict(X)
    arr = np.asarray(pred, dtype=float)
    if arr.ndim > 1:
        arr = arr[:, 0]
    return arr


def _save_base_model(name: str, model) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if name == "xgb":
        model.save_model(XGB_PATH)
    elif name == "lgbm":
        model.booster_.save_model(str(LGBM_PATH))
    elif name == "catboost":
        model.save_model(str(CAT_PATH))


def _load_base_models() -> dict:
    models = {}
    if XGB_PATH.exists():
        model = _build_model()
        model.load_model(str(XGB_PATH))
        models["xgb"] = model
    if LGBM_PATH.exists():
        try:
            from lightgbm import Booster

            models["lgbm"] = Booster(model_file=str(LGBM_PATH))
        except Exception:
            pass
    if CAT_PATH.exists():
        try:
            from catboost import CatBoostClassifier

            model = CatBoostClassifier()
            model.load_model(str(CAT_PATH))
            models["catboost"] = model
        except Exception:
            pass
    return models


def _bundle_predict_probability(base_models: dict, meta_model, X: np.ndarray) -> tuple[np.ndarray, dict]:
    base_probs = {}
    cols = []
    for name in ("xgb", "lgbm", "catboost"):
        model = base_models.get(name)
        if model is None:
            continue
        prob = _predict_proba(model, X)
        base_probs[name] = prob
        cols.append(prob)
    if not cols:
        return np.zeros(len(X)), {}
    stacked = np.column_stack(cols)
    if meta_model is None:
        ensemble = stacked.mean(axis=1)
    else:
        ensemble = meta_model.predict_proba(stacked)[:, 1]
    return ensemble, {k: float(v[0]) for k, v in base_probs.items()}


def train_model(symbols: list[str] | None = None, period: str = "5y") -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score

    X, y, data = load_training_data(symbols=symbols, period=period)
    if X is None or y is None or data is None or len(X) < 500:
        return {"error": "학습 데이터 부족"}

    split_idx = int(len(data) * 0.8)
    train = data.iloc[:split_idx]
    test = data.iloc[split_idx:]
    if len(train) < 300 or len(test) < 100:
        return {"error": "학습/검증 분할 부족"}

    train_split_idx = int(len(train) * 0.8)
    subtrain = train.iloc[:train_split_idx]
    meta_holdout = train.iloc[train_split_idx:]

    X_sub = subtrain[FEATURE_NAMES].astype(float).to_numpy()
    y_sub = subtrain["label"].astype(int).to_numpy()
    X_meta = meta_holdout[FEATURE_NAMES].astype(float).to_numpy()
    y_meta = meta_holdout["label"].astype(int).to_numpy()
    X_train = train[FEATURE_NAMES].astype(float).to_numpy()
    y_train = train["label"].astype(int).to_numpy()
    X_test = test[FEATURE_NAMES].astype(float).to_numpy()
    y_test = test["label"].astype(int).to_numpy()

    pos = max(int(y_sub.sum()), 1)
    neg = max(len(y_sub) - pos, 1)
    scale_pos_weight = neg / pos
    base_models = {
        "xgb": _build_model(scale_pos_weight=scale_pos_weight),
        "lgbm": _build_lgbm_model(scale_pos_weight=scale_pos_weight),
        "catboost": _build_catboost_model(scale_pos_weight=scale_pos_weight),
    }
    base_models = {k: v for k, v in base_models.items() if v is not None}

    meta_cols = []
    usable_names = []
    for name, model in base_models.items():
        fitted = _fit_model(model, X_sub, y_sub, X_meta, y_meta)
        if fitted is None:
            continue
        prob = _predict_proba(fitted, X_meta)
        meta_cols.append(prob)
        usable_names.append(name)

    if not usable_names:
        return {"error": "학습 가능한 base model 없음"}

    meta_model = None
    if len(meta_cols) >= 2 and len(np.unique(y_meta)) >= 2:
        meta_X = np.column_stack(meta_cols)
        meta_model = LogisticRegression(max_iter=1000, random_state=42)
        meta_model.fit(meta_X, y_meta)

    final_models = {}
    for name in usable_names:
        fitted = _fit_model(base_models[name], X_train, y_train, X_test, y_test)
        if fitted is not None:
            final_models[name] = fitted
            _save_base_model(name, fitted)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(META_PATH, "wb") as fp:
        pickle.dump(meta_model, fp)

    ensemble_prob, _ = _bundle_predict_probability(final_models, meta_model, X_test)
    result = {
        "samples": int(len(data)),
        "train_samples": int(len(train)),
        "test_samples": int(len(test)),
        "buy_ratio": round(float(y.mean()), 4),
        "oos_auc": round(float(roc_auc_score(y_test, ensemble_prob)), 4) if len(np.unique(y_test)) > 1 else None,
        "oos_ap": round(float(average_precision_score(y_test, ensemble_prob)), 4) if len(np.unique(y_test)) > 1 else None,
        "base_models": list(final_models.keys()),
        "thresholds": {"buy": BUY_THRESHOLD},
        "feature_names": FEATURE_NAMES,
    }
    META_JSON_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _load_bundle() -> tuple[dict, object | None, dict]:
    base_models = _load_base_models()
    meta_model = None
    if META_PATH.exists():
        try:
            with open(META_PATH, "rb") as fp:
                meta_model = pickle.load(fp)
        except Exception:
            meta_model = None
    meta = {}
    if META_JSON_PATH.exists():
        try:
            meta = json.loads(META_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return base_models, meta_model, meta


def predict_stock(symbol: str) -> dict:
    base_models, meta_model, meta = _load_bundle()
    if not base_models:
        return {"error": "모델 없음. train 먼저 실행"}

    frame = _build_feature_frame(symbol, period="2y")
    if frame.empty:
        return {"error": f"{symbol} 피처 생성 실패"}

    latest = frame.iloc[-1]
    X = latest[FEATURE_NAMES].astype(float).to_numpy().reshape(1, -1)
    prob, base_probs = _bundle_predict_probability(base_models, meta_model, X)
    prob_pct = round(float(prob[0]) * 100.0, 1)
    buy_threshold = float(meta.get("thresholds", {}).get("buy", BUY_THRESHOLD))
    action = "BUY" if float(prob[0]) >= buy_threshold else "HOLD"
    return {
        "symbol": symbol,
        "action": action,
        "buy_probability": prob_pct,
        "model_type": "ensemble" if meta_model is not None else "base_average",
        "base_probabilities": {k: round(v * 100.0, 1) for k, v in base_probs.items()},
        "features": {name: round(float(latest[name]), 6) for name in FEATURE_NAMES},
    }


def get_ml_signal(symbol: str) -> dict:
    try:
        pred = predict_stock(symbol)
        if "error" in pred:
            return {"action": "HOLD", "confidence": 0.0, "source": f"US_ML_ERROR: {pred['error']}"}
        return {
            "action": pred["action"],
            "confidence": float(pred["buy_probability"]),
            "source": "US_ML_ENSEMBLE",
            "base_probabilities": pred.get("base_probabilities", {}),
        }
    except Exception as exc:
        return {"action": "HOLD", "confidence": 0.0, "source": f"US_ML_ERROR: {exc}"}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "train":
        result = train_model()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "predict" and len(sys.argv) > 2:
        result = predict_stock(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("사용법:")
        print("  python3 us_ml_model.py train")
        print("  python3 us_ml_model.py predict AAPL")
