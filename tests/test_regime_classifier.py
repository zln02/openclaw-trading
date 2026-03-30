from __future__ import annotations

from datetime import date

import numpy as np

from agents.regime_classifier import FEATURE_NAMES, RegimeClassifier, _features_to_array


def test_classify_returns_known_regime(monkeypatch) -> None:
    classifier = RegimeClassifier()
    monkeypatch.setattr(
        classifier,
        "get_features",
        lambda as_of=None: {
            "spy_ret_5d": 0.03,
            "spy_ret_20d": 0.08,
            "spy_vol_20d": 0.01,
            "vix_level": 18.0,
            "vix_ret_5d": -0.02,
            "vix_term_proxy": -1.0,
            "ret_skew_60d": 0.2,
            "ret_kurt_60d": 2.5,
            "credit_spread_proxy": 0.01,
            "corr_shift_20_60": 0.01,
        },
    )

    result = classifier.classify(use_model=False)

    assert result["regime"] in {"RISK_ON", "RISK_OFF", "TRANSITION", "CRISIS"}, "classify() must return a known regime"


def test_classify_empty_features_defaults_transition(monkeypatch) -> None:
    classifier = RegimeClassifier()
    monkeypatch.setattr(classifier, "get_features", lambda as_of=None: {})

    result = classifier.classify(use_model=False)

    assert result["regime"] == "TRANSITION", "empty features should fall back to TRANSITION"


def test_features_to_array_preserves_feature_order() -> None:
    features = {"spy_ret_5d": 1.0, "vix_level": 20.0}

    arr = _features_to_array(features)

    assert isinstance(arr, list), "_features_to_array() should return a list-compatible array"
    assert len(arr) == len(FEATURE_NAMES), "feature array length should match FEATURE_NAMES"
    assert arr[FEATURE_NAMES.index("spy_ret_5d")] == 1.0, "spy_ret_5d should keep its position"
    assert arr[FEATURE_NAMES.index("vix_level")] == 20.0, "vix_level should keep its position"


def test_features_to_array_missing_keys_default_zero() -> None:
    arr = _features_to_array({})

    assert all(v == 0.0 for v in arr), "missing feature keys should default to 0.0"


def test_train_from_rule_labels_with_sufficient_samples(monkeypatch) -> None:
    classifier = RegimeClassifier()

    def fake_get_features(as_of=None):
        day = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
        month = day.month if isinstance(day, date) else 1
        return {
            "spy_ret_5d": month * 0.001,
            "spy_ret_20d": month * 0.002,
            "spy_vol_20d": 0.01 + month * 0.0001,
            "vix_level": 15.0 + month,
            "vix_ret_5d": 0.001,
            "vix_term_proxy": 0.0,
            "ret_skew_60d": 0.1,
            "ret_kurt_60d": 2.0,
            "credit_spread_proxy": 0.01,
            "corr_shift_20_60": 0.01,
        }

    class FakeModel:
        def fit(self, X, y):
            self.fitted_shape = (len(X), len(y))

        def save_model(self, path):
            self.saved_path = path

    monkeypatch.setattr(classifier, "get_features", fake_get_features)
    monkeypatch.setattr("xgboost.XGBClassifier", lambda *args, **kwargs: FakeModel())
    monkeypatch.setattr(
        "sklearn.model_selection.cross_val_score",
        lambda model, X, y, cv, scoring: np.array([0.7, 0.8, 0.9]),
    )

    result = classifier.train_from_rule_labels(years=5)

    assert result["ok"] is True, "training should succeed when 50+ monthly samples are available"
    assert result["samples"] >= 50, "training sample count should reflect generated monthly rows"


def test_train_from_rule_labels_with_too_few_samples(monkeypatch) -> None:
    classifier = RegimeClassifier()

    monkeypatch.setattr(classifier, "get_features", lambda as_of=None: {"vix_level": 20.0})
    monkeypatch.setattr("agents.regime_classifier.datetime", type("FakeDateTime", (), {
        "now": staticmethod(lambda tz=None: __import__("datetime").datetime(2026, 3, 30, tzinfo=tz)),
    }))

    result = classifier.train_from_rule_labels(years=0)

    assert result["ok"] is False, "training should fail when there are too few samples"
    assert "not enough samples" in result["error"], "too-few-samples error should be explicit"
