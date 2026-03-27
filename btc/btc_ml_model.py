#!/usr/bin/env python3
"""BTC 단기 방향성 예측 모델 스켈레톤.

- 입력 데이터: Upbit 5분/15분/1시간봉 + 보조 대체데이터
- 피처: RSI, MACD, Bollinger Band, 거래량 비율, 김치프리미엄, Fear&Greed
- 타겟: 1시간 후 수익률이 +0.5% 이상이면 1, 아니면 0

실제 학습은 데이터 적재 상태를 확인한 뒤 별도 튜닝이 필요하다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common.logger import get_logger
from common.supabase_client import get_supabase

log = get_logger("btc_ml_model")

try:
    import pyupbit
except ImportError:  # pragma: no cover - optional runtime dependency
    pyupbit = None


MODEL_DIR = Path(__file__).resolve().parents[1] / "brain" / "ml" / "btc"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
FEATURE_COLS = [
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "bb_pos",
    "volume_ratio_20",
    "kimchi_premium",
    "fear_greed",
    "rsi_14_1h",
    "ma_ratio_1h",
    "volatility_20",
    "volatility_ratio",
]


@dataclass
class BtcDatasetConfig:
    symbol: str = "KRW-BTC"
    interval: str = "minute5"
    count: int = 2000
    target_horizon_bars: int = 12  # 5분봉 기준 1시간
    target_return: float = 0.005


class BtcMlDatasetBuilder:
    """BTC 학습용 시계열 데이터셋 생성기."""

    def __init__(self, supabase=None):
        self.supabase = supabase or get_supabase()

    def load_from_supabase(self, limit: int = 5000) -> pd.DataFrame:
        if not self.supabase:
            return pd.DataFrame()
        try:
            rows = (
                self.supabase.table("btc_candles")
                .select("*")
                .order("timestamp", desc=False)
                .limit(limit)
                .execute()
                .data
                or []
            )
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            log.info(f"btc_candles 로드: {len(df)}건")
            return df
        except Exception as e:
            log.warning(f"btc_candles 조회 실패: {e}")
            return pd.DataFrame()

    def load_from_pyupbit(self, config: BtcDatasetConfig) -> pd.DataFrame:
        if pyupbit is None:
            log.warning("pyupbit 미설치 또는 import 실패")
            return pd.DataFrame()
        try:
            df = pyupbit.get_ohlcv(config.symbol, interval=config.interval, count=config.count)
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.reset_index().rename(columns={"index": "timestamp"})
            log.info(f"pyupbit 캔들 로드: {len(df)}건")
            return df
        except Exception as e:
            log.warning(f"pyupbit 캔들 조회 실패: {e}")
            return pd.DataFrame()

    def load_training_frame(self, config: BtcDatasetConfig) -> pd.DataFrame:
        df = self.load_from_supabase()
        if df.empty:
            df = self.load_from_pyupbit(config)
        return df


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _calc_macd(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """기본 기술지표 피처 생성."""
    if frame.empty:
        return frame

    df = frame.copy()
    close_col = "close" if "close" in df.columns else "close_price"
    volume_col = "volume" if "volume" in df.columns else "volume_krw"
    df["close"] = pd.to_numeric(df[close_col], errors="coerce")
    df["volume"] = pd.to_numeric(df.get(volume_col, 0), errors="coerce").fillna(0)

    df["rsi_14"] = _calc_rsi(df["close"], 14)
    macd, signal = _calc_macd(df["close"])
    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    ma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    df["bb_upper"] = ma20 + 2 * std20
    df["bb_lower"] = ma20 - 2 * std20
    band_width = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
    df["bb_pos"] = ((df["close"] - df["bb_lower"]) / band_width).clip(0, 1)
    df["volume_ratio_20"] = df["volume"] / df["volume"].rolling(20).mean()

    try:
        import pyupbit
        upbit_price = pyupbit.get_current_price("KRW-BTC")
        import requests
        binance_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=5,
        )
        binance_price = float(binance_resp.json()["price"])
        fx_resp = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        usd_krw = fx_resp.json()["rates"]["KRW"]
        kimchi = ((upbit_price / (binance_price * usd_krw)) - 1) * 100
    except Exception:
        kimchi = 0.0
    df["kimchi_premium"] = kimchi

    try:
        import requests
        response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        fear_greed = int(response.json()["data"][0]["value"])
    except Exception:
        fear_greed = 50.0
    df["fear_greed"] = fear_greed

    if len(df) >= 12:
        close_1h = df["close"].rolling(12).apply(lambda x: x.iloc[-1], raw=False)
        df["rsi_14_1h"] = _calc_rsi(close_1h, 14)
        df["ma_ratio_1h"] = df["close"] / df["close"].rolling(60).mean()
    else:
        df["rsi_14_1h"] = df["rsi_14"]
        df["ma_ratio_1h"] = 1.0

    returns = df["close"].pct_change()
    df["volatility_20"] = returns.rolling(20).std()
    df["volatility_ratio"] = returns.rolling(5).std() / returns.rolling(20).std().clip(lower=1e-8)
    return df


def build_training_dataset(
    frame: pd.DataFrame,
    config: BtcDatasetConfig,
) -> tuple[pd.DataFrame, pd.Series]:
    """피처/타겟 생성."""
    df = build_features(frame)
    if df.empty:
        return pd.DataFrame(), pd.Series(dtype=int)

    future_close = df["close"].shift(-config.target_horizon_bars)
    future_ret = (future_close / df["close"]) - 1.0
    df["target"] = (future_ret >= config.target_return).astype(int)

    clean = df.dropna(subset=FEATURE_COLS + ["target"]).copy()
    X = clean[FEATURE_COLS]
    y = clean["target"].astype(int)
    return X, y


def build_model(**kwargs: Any):
    """XGBoost 기본 모델 생성."""
    from xgboost import XGBClassifier

    params = {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "eval_metric": "logloss",
        "random_state": 42,
    }
    params.update(kwargs)
    return XGBClassifier(**params)


def build_lgbm_model(**kwargs: Any):
    """LightGBM 모델."""
    try:
        from lightgbm import LGBMClassifier
    except Exception as e:
        log.warning(f"LightGBM import 실패: {e}")
        return None

    params = {
        "n_estimators": 200,
        "learning_rate": 0.05,
        "max_depth": 5,
        "num_leaves": 31,
        "random_state": 42,
        "verbose": -1,
    }
    params.update(kwargs)
    return LGBMClassifier(**params)


def build_catboost_model(**kwargs: Any):
    """CatBoost 모델."""
    try:
        from catboost import CatBoostClassifier
    except Exception as e:
        log.warning(f"CatBoost import 실패: {e}")
        return None

    params = {
        "iterations": 200,
        "learning_rate": 0.05,
        "depth": 5,
        "random_seed": 42,
        "verbose": 0,
    }
    params.update(kwargs)
    return CatBoostClassifier(**params)


def build_stacking_model(X_train: pd.DataFrame, y_train: pd.Series):
    """XGB + LGBM + CatBoost 스태킹 모델."""
    try:
        from sklearn.ensemble import StackingClassifier
        from sklearn.linear_model import LogisticRegression
    except Exception as e:
        log.warning(f"StackingClassifier import 실패: {e}")
        return None

    estimators = [("xgb", build_model())]
    lgbm = build_lgbm_model()
    if lgbm is not None:
        estimators.append(("lgbm", lgbm))
    catboost = build_catboost_model()
    if catboost is not None:
        estimators.append(("cb", catboost))

    if len(estimators) < 2:
        log.warning("스태킹 모델 생성 실패: 베이스 모델 부족")
        return None

    model = StackingClassifier(
        estimators=estimators,
        final_estimator=LogisticRegression(max_iter=1000),
        cv=5,
        stack_method="predict_proba",
    )
    model.fit(X_train, y_train)
    return model


def predict_btc_direction(model, features_df: pd.DataFrame) -> dict[str, Any]:
    """BTC 방향성 예측."""
    probabilities = model.predict_proba(features_df)[-1]
    down_prob = float(probabilities[0])
    up_prob = float(probabilities[1])
    direction = "UP" if up_prob >= down_prob else "DOWN"
    confidence = max(up_prob, down_prob)
    return {
        "direction": direction,
        "confidence": confidence,
        "probabilities": {
            "up": up_prob,
            "down": down_prob,
        },
    }


def save_btc_models(models: dict[str, Any], model_dir: Path = MODEL_DIR) -> None:
    """앙상블 모델 저장."""
    import joblib

    model_dir.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        if model is None:
            continue
        path = model_dir / f"btc_{name}_model.pkl"
        joblib.dump(model, path)
    log.info(f"BTC 앙상블 모델 저장: {model_dir}")


def load_btc_models(model_dir: Path = MODEL_DIR) -> dict[str, Any]:
    """앙상블 모델 로드."""
    import joblib

    loaded: dict[str, Any] = {}
    for name in ("xgb", "lgbm", "catboost", "stacking"):
        path = model_dir / f"btc_{name}_model.pkl"
        if not path.exists():
            continue
        try:
            loaded[name] = joblib.load(path)
        except Exception as e:
            log.warning(f"BTC {name} 모델 로드 실패: {e}")
    return loaded


def train_btc_ensemble(config: BtcDatasetConfig | None = None) -> dict[str, Any]:
    """BTC 앙상블 학습."""
    cfg = config or BtcDatasetConfig()
    builder = BtcMlDatasetBuilder()
    frame = builder.load_training_frame(cfg)
    if frame.empty:
        return {"ok": False, "error": "학습 데이터 없음"}

    X, y = build_training_dataset(frame, cfg)
    if X.empty or len(X) < 200:
        return {"ok": False, "error": f"학습 데이터 부족: {len(X)}"}

    try:
        from sklearn.metrics import accuracy_score
    except Exception as e:
        return {"ok": False, "error": f"sklearn import 실패: {e}"}

    split_idx = int(len(X) * 0.8)
    X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]
    X_valid, y_valid = X.iloc[split_idx:], y.iloc[split_idx:]

    models: dict[str, Any] = {
        "xgb": build_model(),
        "lgbm": build_lgbm_model(),
        "catboost": build_catboost_model(),
    }

    metrics: dict[str, float] = {}
    for name, model in list(models.items()):
        if model is None:
            continue
        try:
            model.fit(X_train, y_train)
            preds = model.predict(X_valid)
            acc = float(accuracy_score(y_valid, preds))
            metrics[name] = acc
            log.info(f"BTC {name} accuracy: {acc:.4f}")
        except Exception as e:
            log.warning(f"BTC {name} 학습 실패: {e}")
            models[name] = None

    stacking = build_stacking_model(X_train, y_train)
    models["stacking"] = stacking
    if stacking is not None:
        try:
            stacking_preds = stacking.predict(X_valid)
            stacking_acc = float(accuracy_score(y_valid, stacking_preds))
            metrics["stacking"] = stacking_acc
            log.info(f"BTC stacking accuracy: {stacking_acc:.4f}")
        except Exception as e:
            log.warning(f"BTC stacking 평가 실패: {e}")

    save_btc_models(models, MODEL_DIR)

    try:
        from common.telegram import send_telegram

        lines = ["🤖 BTC 앙상블 학습 완료"]
        for name, score in metrics.items():
            lines.append(f"- {name}: accuracy={score:.4f}")
        send_telegram("\n".join(lines))
    except Exception as e:
        log.warning(f"BTC 앙상블 텔레그램 알림 실패: {e}")

    return {
        "ok": True,
        "samples": len(X),
        "feature_columns": list(X.columns),
        "metrics": metrics,
        "saved_models": [name for name, model in models.items() if model is not None],
    }


def train_btc_model(config: BtcDatasetConfig | None = None) -> dict[str, Any]:
    """학습 스켈레톤.

    실제 운영용 학습 전 점검 포인트:
    - Supabase `btc_candles` 스키마 확인
    - 멀티 타임프레임 병합
    - 김프/Fear&Greed 히스토리 적재 확인
    - 시계열 split 기반 검증 추가
    """
    cfg = config or BtcDatasetConfig()
    builder = BtcMlDatasetBuilder()
    frame = builder.load_training_frame(cfg)
    if frame.empty:
        return {"ok": False, "error": "학습 데이터 없음"}

    X, y = build_training_dataset(frame, cfg)
    if X.empty or len(X) < 200:
        return {"ok": False, "error": f"학습 데이터 부족: {len(X)}"}

    model = build_model()
    split_idx = int(len(X) * 0.8)
    X_train, y_train = X.iloc[:split_idx], y.iloc[:split_idx]
    X_valid, y_valid = X.iloc[split_idx:], y.iloc[split_idx:]
    model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)

    out_path = MODEL_DIR / "btc_xgb_model.ubj"
    model.save_model(str(out_path))
    log.info(f"BTC 모델 저장: {out_path}")
    return {
        "ok": True,
        "samples": len(X),
        "feature_columns": list(X.columns),
        "model_path": str(out_path),
    }


if __name__ == "__main__":
    result = train_btc_model()
    print(result)
