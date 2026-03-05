#!/usr/bin/env python3
"""
주식 매매 ML 모델 v1.0

XGBoost 분류 모델:
- 입력: 기술적 지표 + 가격/거래량 특성
- 출력: 3일 내 +2% 이상 상승 확률

사용법:
    python3 stocks/ml_model.py train          # 모델 학습
    python3 stocks/ml_model.py evaluate       # 성과 평가(=train)
    python3 stocks/ml_model.py predict 005930 # 특정 종목 예측
    python3 stocks/ml_model.py predict_all    # 전체 종목 예측
"""

import os
import json
import sys
import pickle
from pathlib import Path

import numpy as np


def _load_env():
    p = Path('/home/wlsdud5035/.openclaw/openclaw.json')
    if p.exists():
        d = json.loads(p.read_text())
        for k, v in (d.get('env') or {}).items():
            if isinstance(v, str):
                os.environ.setdefault(k, v)


_load_env()

from supabase import create_client  # noqa: E402

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SECRET_KEY', '')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

MODEL_PATH = Path(__file__).parent / 'xgb_model.pkl'
FEATURE_NAMES = [
    'rsi_14',
    'rsi_7',
    'macd',
    'macd_histogram',
    'macd_signal',
    'bb_pos',
    'bb_width_pct',
    'vol_ratio_5',
    'vol_ratio_20',
    'return_1d',
    'return_3d',
    'return_5d',
    'return_10d',
    'return_20d',
    'high_low_range',
    'close_vs_ma5',
    'close_vs_ma20',
    'close_vs_ma60',
    'atr_14',
    'volume_trend',
]


# ─────────────────────────────────────────────
# 피처 계산
# ─────────────────────────────────────────────
def calc_ema(data, period):
    if len(data) < period:
        return data[-1] if data else 0
    k = 2 / (period + 1)
    e = data[0]
    for d in data[1:]:
        e = d * k + e * (1 - k)
    return e


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(-period, 0):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs) / period


def extract_features(closes, volumes, highs, lows, idx):
    """특정 시점(idx)에서 피처 벡터 추출"""
    if idx < 60:  # 최소 60일 필요
        return None

    c = closes[: idx + 1]
    v = volumes[: idx + 1]
    h = highs[: idx + 1]
    l = lows[: idx + 1]

    price = c[-1]
    if price <= 0:
        return None

    # RSI
    rsi_14 = calc_rsi(c, 14)
    rsi_7 = calc_rsi(c, 7)

    # MACD
    ema12 = calc_ema(c, 12)
    ema26 = calc_ema(c, 26)
    macd = ema12 - ema26

    macd_line = []
    for i in range(26, len(c)):
        e12 = calc_ema(c[: i + 1], 12)
        e26 = calc_ema(c[: i + 1], 26)
        macd_line.append(e12 - e26)
    macd_sig = calc_ema(macd_line, 9) if len(macd_line) >= 9 else macd
    macd_hist = macd - macd_sig

    # 볼린저 밴드
    ma20 = sum(c[-20:]) / 20
    std20 = (sum((x - ma20) ** 2 for x in c[-20:]) / 20) ** 0.5
    bb_upper = ma20 + 2 * std20
    bb_lower = ma20 - 2 * std20
    bb_width = bb_upper - bb_lower
    bb_pos = (price - bb_lower) / bb_width * 100 if bb_width > 0 else 50
    bb_width_pct = bb_width / ma20 * 100 if ma20 > 0 else 0

    # 거래량
    avg_vol_5 = sum(v[-6:-1]) / 5 if len(v) >= 6 else 1
    avg_vol_20 = sum(v[-21:-1]) / 20 if len(v) >= 21 else 1
    vol_ratio_5 = v[-1] / avg_vol_5 if avg_vol_5 > 0 else 1
    vol_ratio_20 = v[-1] / avg_vol_20 if avg_vol_20 > 0 else 1

    # 수익률
    return_1d = (c[-1] / c[-2] - 1) * 100 if len(c) >= 2 else 0
    return_3d = (c[-1] / c[-4] - 1) * 100 if len(c) >= 4 else 0
    return_5d = (c[-1] / c[-6] - 1) * 100 if len(c) >= 6 else 0
    return_10d = (c[-1] / c[-11] - 1) * 100 if len(c) >= 11 else 0
    return_20d = (c[-1] / c[-21] - 1) * 100 if len(c) >= 21 else 0

    # 일일 고저 범위
    high_low_range = (h[-1] - l[-1]) / price * 100

    # 이동평균 대비
    ma5 = sum(c[-5:]) / 5
    ma60 = sum(c[-60:]) / 60 if len(c) >= 60 else ma20
    close_vs_ma5 = (price / ma5 - 1) * 100
    close_vs_ma20 = (price / ma20 - 1) * 100
    close_vs_ma60 = (price / ma60 - 1) * 100

    # ATR
    atr = calc_atr(h, l, c, 14)
    atr_pct = atr / price * 100 if price > 0 else 0

    # 거래량 추세
    vol_trend = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1

    # 일부 피처는 가격으로 정규화
    return [
        rsi_14,
        rsi_7,
        macd / price * 100,
        macd_hist / price * 100,
        macd_sig / price * 100,
        bb_pos,
        bb_width_pct,
        vol_ratio_5,
        vol_ratio_20,
        return_1d,
        return_3d,
        return_5d,
        return_10d,
        return_20d,
        high_low_range,
        close_vs_ma5,
        close_vs_ma20,
        close_vs_ma60,
        atr_pct,
        vol_trend,
    ]


# ─────────────────────────────────────────────
# 데이터 준비
# ─────────────────────────────────────────────
def load_training_data(target_days=3, target_return=0.02):
    """
    DB에서 학습 데이터 생성

    라벨: target_days일 후 수익률 >= target_return이면 1(매수), 아니면 0(관망)
    """
    if not supabase:
        print('Supabase 미연결')
        return None, None

    stocks = (
        supabase.table('top50_stocks')
        .select('stock_code')
        .execute()
        .data
        or []
    )
    print(f'데이터 로드: {len(stocks)}종목')

    all_X = []
    all_y = []

    for s in stocks:
        code = s['stock_code']
        rows = (
            supabase.table('daily_ohlcv')
            .select('date,open_price,high_price,low_price,close_price,volume')
            .eq('stock_code', code)
            .order('date', desc=False)
            .execute()
            .data
            or []
        )

        if len(rows) < 80:
            continue

        closes = [float(r['close_price']) for r in rows]
        volumes = [float(r.get('volume', 0)) for r in rows]
        highs = [float(r.get('high_price', r['close_price'])) for r in rows]
        lows = [float(r.get('low_price', r['close_price'])) for r in rows]

        for i in range(60, len(rows) - target_days):
            features = extract_features(closes, volumes, highs, lows, i)
            if features is None:
                continue

            future_return = (closes[i + target_days] - closes[i]) / closes[i]
            label = 1 if future_return >= target_return else 0

            all_X.append(features)
            all_y.append(label)

    if not all_X:
        print('학습 데이터 없음')
        return None, None

    X = np.array(all_X, dtype=float)
    y = np.array(all_y, dtype=int)
    buys = int(y.sum())
    print(f'학습 데이터: {len(X)}개 샘플 (매수: {buys} / 관망: {len(y) - buys})')
    if len(y) > 0:
        print(f'매수 비율: {buys / len(y) * 100:.1f}%')

    return X, y


# ─────────────────────────────────────────────
# 모델 학습
# ─────────────────────────────────────────────
def _build_model(scale_pos_weight: float = 1.0):
    """XGBClassifier 인스턴스 공통 생성."""
    from xgboost import XGBClassifier
    return XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric='logloss',
        random_state=42,
        use_label_encoder=False,
    )


def walk_forward_validate(X: np.ndarray, y: np.ndarray, n_splits: int = 5) -> dict:
    """
    Walk-forward 교차검증 (시계열 전용).

    각 폴드에서 과거로 학습 → 미래로 검증.
    랜덤 분할 금지 (미래 데이터 누수 방지).

    Returns:
        {
          'fold_aucs': list[float],
          'fold_precisions': list[float],
          'mean_auc': float,
          'mean_precision': float,
          'std_auc': float,
        }
    """
    try:
        from xgboost import XGBClassifier
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import roc_auc_score, precision_score
    except ImportError as e:
        print(f'의존성 부족: {e}')
        return {}

    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_aucs, fold_precisions = [], []

    print(f'\n=== Walk-forward 교차검증 ({n_splits}폴드) ===')
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        if len(np.unique(y_te)) < 2:
            continue  # 라벨 단일 폴드 스킵

        pos = max(int(y_tr.sum()), 1)
        neg = max(len(y_tr) - pos, 1)
        model = _build_model(scale_pos_weight=neg / pos)
        model.fit(X_tr, y_tr, verbose=False)

        y_prob = model.predict_proba(X_te)[:, 1]
        y_pred = (y_prob >= 0.65).astype(int)

        auc = roc_auc_score(y_te, y_prob)
        prec = precision_score(y_te, y_pred, zero_division=0)

        fold_aucs.append(auc)
        fold_precisions.append(prec)
        print(f'  Fold {fold}: AUC={auc:.3f}  Precision@0.65={prec:.3f}  '
              f'(train={len(X_tr)}, test={len(X_te)})')

    if not fold_aucs:
        return {}

    result = {
        'fold_aucs':       fold_aucs,
        'fold_precisions': fold_precisions,
        'mean_auc':        round(float(np.mean(fold_aucs)), 4),
        'std_auc':         round(float(np.std(fold_aucs)), 4),
        'mean_precision':  round(float(np.mean(fold_precisions)), 4),
    }
    print(f'\n  평균 AUC: {result["mean_auc"]:.3f} ± {result["std_auc"]:.3f}')
    print(f'  평균 Precision@0.65: {result["mean_precision"]:.3f}')
    return result


def compute_shap_values(model, X_sample: np.ndarray) -> dict:
    """
    SHAP 값으로 피처 기여도 분석.

    Args:
        model: 학습된 XGBClassifier
        X_sample: 분석할 샘플 (최대 500개 사용)

    Returns:
        {'feature': shap_mean_abs, ...} — 내림차순 정렬
    """
    try:
        import shap
    except ImportError:
        print('shap 미설치: pip install shap')
        return {}

    sample = X_sample[:500] if len(X_sample) > 500 else X_sample
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(sample)

    # 이진 분류: shap_vals shape = (n_samples, n_features)
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]  # 클래스 1 (매수)

    mean_abs = np.abs(shap_vals).mean(axis=0)
    ranking = sorted(
        zip(FEATURE_NAMES, mean_abs.tolist()),
        key=lambda x: x[1], reverse=True,
    )

    print('\n=== SHAP 피처 기여도 (평균 절댓값) ===')
    for name, val in ranking[:10]:
        bar = '█' * int(val * 200)
        print(f'  {name:<20} {val:.4f}  {bar}')

    return {name: round(val, 6) for name, val in ranking}


def train_model():
    """XGBoost 모델 학습 (Walk-forward + SHAP + AUC 포함)."""
    try:
        from xgboost import XGBClassifier
    except ImportError:
        print('xgboost 미설치. pip install xgboost')
        return

    from sklearn.metrics import (
        classification_report, accuracy_score,
        roc_auc_score, average_precision_score,
    )

    X, y = load_training_data(target_days=3, target_return=0.02)
    if X is None or len(X) < 100:
        print('데이터 부족 (최소 100개 필요)')
        return

    # ── Walk-forward 교차검증 ──
    wf = walk_forward_validate(X, y, n_splits=5)

    # ── 최종 모델: 앞 80% 학습 / 뒤 20% OOS 테스트 ──
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f'\n최종 모델 학습: {len(X_train)}개 / OOS 테스트: {len(X_test)}개')

    pos = max(int(y_train.sum()), 1)
    neg = max(len(y_train) - pos, 1)
    model = _build_model(scale_pos_weight=neg / pos)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    print('\n=== OOS 모델 성과 ===')
    print(f'  정확도:     {accuracy_score(y_test, y_pred) * 100:.1f}%')
    if len(np.unique(y_test)) > 1:
        print(f'  AUC-ROC:    {roc_auc_score(y_test, y_prob):.3f}')
        print(f'  AP (PR):    {average_precision_score(y_test, y_prob):.3f}')
    print(classification_report(y_test, y_pred, target_names=['관망', '매수']))

    # ── XGBoost 피처 중요도 ──
    importances = sorted(
        zip(FEATURE_NAMES, model.feature_importances_),
        key=lambda x: x[1], reverse=True,
    )
    print('\n=== XGBoost 피처 중요도 TOP 10 ===')
    for name, imp in importances[:10]:
        print(f'  {name}: {imp:.4f}')

    # ── SHAP 분석 ──
    shap_ranking = compute_shap_values(model, X_test)

    # ── 확률 임계값별 승률 ──
    thresholds = [0.5, 0.6, 0.65, 0.7, 0.8]
    print('\n=== 확률 임계값별 Precision ===')
    for thresh in thresholds:
        mask = y_prob >= thresh
        if mask.sum() == 0:
            continue
        prec = y_test[mask].sum() / mask.sum() * 100
        print(f'  ≥{thresh:.2f}: {int(mask.sum())}건 → Precision {prec:.1f}%')

    # ── 모델 메타데이터와 함께 저장 ──
    meta = {
        'walk_forward': wf,
        'shap_ranking': list(shap_ranking.items())[:10] if shap_ranking else [],
        'trained_at': str(Path(__file__).stat().st_mtime),
        'n_samples': len(X),
        'feature_importance': [(n, round(float(v), 6)) for n, v in importances],
    }
    META_PATH = MODEL_PATH.with_suffix('.meta.json')
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    os.chmod(MODEL_PATH, 0o666)  # 어느 유저든 다음 저장 가능하도록
    print(f'\n모델 저장: {MODEL_PATH}')
    print(f'메타 저장: {META_PATH}')

    return model


def retrain_from_live_trades(min_samples: int = 30) -> bool:
    """
    실제 매매 결과(trade_executions)로 모델 재학습 (온라인 학습).

    XGBoost의 incremental fit은 부재 → 전체 재학습이지만
    라이브 거래 라벨(성공/실패)을 추가 학습 데이터로 포함.

    Args:
        min_samples: 재학습 최소 라이브 샘플 수

    Returns:
        True if 재학습 성공
    """
    if not supabase:
        print('Supabase 미연결')
        return False

    # 실매매 결과 로드
    try:
        rows = (
            supabase.table('trade_executions')
            .select('stock_code,price,result,pnl_pct,created_at')
            .in_('result', ['CLOSED', 'SELL'])
            .order('created_at', desc=False)
            .execute()
            .data or []
        )
    except Exception as e:
        print(f'거래 데이터 로드 실패: {e}')
        return False

    if len(rows) < min_samples:
        print(f'라이브 샘플 부족: {len(rows)} < {min_samples}')
        return False

    # 라이브 라벨 생성: pnl_pct >= 2% → 1(성공)
    live_X, live_y = [], []
    for r in rows:
        code = r.get('stock_code', '')
        pred = predict_stock(code)
        if 'error' in pred:
            continue
        features = list(pred['features'].values())
        pnl = float(r.get('pnl_pct') or 0)
        label = 1 if pnl >= 2.0 else 0
        live_X.append(features)
        live_y.append(label)

    if len(live_X) < min_samples:
        print(f'유효 라이브 샘플 부족: {len(live_X)}')
        return False

    # 히스토리컬 데이터와 병합
    X_hist, y_hist = load_training_data()
    if X_hist is not None and len(X_hist) > 0:
        X_all = np.vstack([X_hist, np.array(live_X, dtype=float)])
        y_all = np.concatenate([y_hist, np.array(live_y, dtype=int)])
    else:
        X_all = np.array(live_X, dtype=float)
        y_all = np.array(live_y, dtype=int)

    live_wins = sum(live_y)
    print(f'\n실매매 데이터 {len(live_X)}건 추가 (성공: {live_wins} / 실패: {len(live_y)-live_wins})')
    print(f'전체 학습 데이터: {len(X_all)}건')

    # 재학습
    pos = max(int(y_all.sum()), 1)
    neg = max(len(y_all) - pos, 1)
    model = _build_model(scale_pos_weight=neg / pos)
    split_idx = int(len(X_all) * 0.85)
    model.fit(
        X_all[:split_idx], y_all[:split_idx],
        eval_set=[(X_all[split_idx:], y_all[split_idx:])],
        verbose=False,
    )

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    os.chmod(MODEL_PATH, 0o666)  # 어느 유저든 다음 저장 가능하도록
    print(f'실매매 반영 모델 저장: {MODEL_PATH}')
    return True


# ─────────────────────────────────────────────
# 예측
# ─────────────────────────────────────────────
def _load_model():
    if not MODEL_PATH.exists():
        return None
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)


def predict_stock(stock_code: str) -> dict:
    """특정 종목 매수 확률 예측"""
    if not supabase:
        return {'error': 'Supabase 미연결'}
    model = _load_model()
    if model is None:
        return {'error': '모델 없음. train 먼저 실행'}

    rows = (
        supabase.table('daily_ohlcv')
        .select('date,open_price,high_price,low_price,close_price,volume')
        .eq('stock_code', stock_code)
        .order('date', desc=False)
        .limit(120)
        .execute()
        .data
        or []
    )

    if len(rows) < 61:
        return {'error': f'데이터 부족: {len(rows)}일'}

    closes = [float(r['close_price']) for r in rows]
    volumes = [float(r.get('volume', 0)) for r in rows]
    highs = [float(r.get('high_price', r['close_price'])) for r in rows]
    lows = [float(r.get('low_price', r['close_price'])) for r in rows]

    features = extract_features(closes, volumes, highs, lows, len(rows) - 1)
    if features is None:
        return {'error': '피처 추출 실패'}

    X = np.array([features], dtype=float)
    prob = float(model.predict_proba(X)[0][1])
    action = 'BUY' if prob >= 0.65 else 'HOLD'

    return {
        'stock_code': stock_code,
        'buy_probability': round(prob * 100, 1),
        'action': action,
        'features': {
            name: round(val, 4) for name, val in zip(FEATURE_NAMES, features)
        },
    }


def predict_all() -> list:
    """전 종목 매수 확률 예측 → 상위 종목 반환"""
    if not supabase:
        print('Supabase 미연결')
        return []
    model = _load_model()
    if model is None:
        print('모델 없음')
        return []

    stocks = (
        supabase.table('top50_stocks')
        .select('stock_code,stock_name')
        .execute()
        .data
        or []
    )
    results = []

    for s in stocks:
        pred = predict_stock(s['stock_code'])
        if 'error' in pred:
            continue
        pred['name'] = s.get('stock_name', s['stock_code'])
        results.append(pred)

    results.sort(key=lambda x: x['buy_probability'], reverse=True)

    print('\n=== 매수 확률 TOP 10 ===')
    for r in results[:10]:
        emoji = '🟢' if r['action'] == 'BUY' else '⚪'
        print(f"  {emoji} {r['name']}: {r['buy_probability']}% → {r['action']}")

    print(f'\n매수 신호: {sum(1 for r in results if r["action"] == "BUY")}종목')
    return results


# ─────────────────────────────────────────────
# trading_agent 연동용 함수
# ─────────────────────────────────────────────
def get_ml_signal(stock_code: str) -> dict:
    """
    trading_agent에서 호출하는 인터페이스

    Returns:
        {
            'action': 'BUY' | 'HOLD',
            'confidence': 0~100,
            'source': 'ML_XGBOOST',
        }
    """
    try:
        pred = predict_stock(stock_code)
        if 'error' in pred:
            return {'action': 'HOLD', 'confidence': 0, 'source': 'ML_ERROR'}

        return {
            'action': pred['action'],
            'confidence': pred['buy_probability'],
            'source': 'ML_XGBOOST',
        }
    except Exception as e:
        return {'action': 'HOLD', 'confidence': 0, 'source': f'ML_ERROR: {e}'}


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'train'

    if cmd == 'train':
        train_model()
    elif cmd == 'predict' and len(sys.argv) > 2:
        result = predict_stock(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif cmd == 'predict_all':
        predict_all()
    elif cmd == 'evaluate':
        train_model()
    elif cmd == 'retrain':
        # 실매매 결과로 재학습
        min_s = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        ok = retrain_from_live_trades(min_samples=min_s)
        print('재학습 성공' if ok else '재학습 실패')
    elif cmd == 'validate':
        # Walk-forward 검증만 실행
        X, y = load_training_data()
        if X is not None:
            walk_forward_validate(X, y)
    elif cmd == 'shap' and len(sys.argv) > 2:
        # 특정 종목 SHAP 분석
        res = predict_stock(sys.argv[2])
        if 'error' not in res:
            model = _load_model()
            if model:
                feats = np.array([list(res['features'].values())], dtype=float)
                compute_shap_values(model, feats)
    else:
        print('사용법:')
        print('  python3 ml_model.py train              # 전체 학습 + Walk-forward + SHAP')
        print('  python3 ml_model.py validate           # Walk-forward 검증만')
        print('  python3 ml_model.py retrain [n]        # 실매매 결과 반영 재학습')
        print('  python3 ml_model.py predict 005930     # 특정 종목 예측')
        print('  python3 ml_model.py shap 005930        # 특정 종목 SHAP 분석')
        print('  python3 ml_model.py predict_all        # 전체 종목 예측')

