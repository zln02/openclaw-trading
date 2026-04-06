"""v6.2 C3: Concept Drift Detector — 예측 품질 모니터링 + 자동 재학습 트리거"""
from collections import deque
from typing import Optional

import numpy as np

from common.logger import get_logger

log = get_logger(__name__)


class ConceptDriftDetector:
    """최근 N건 예측의 AUC를 모니터링하여 드리프트 감지"""

    def __init__(self, window: int = 20, auc_threshold: float = 0.52):
        self.window = window
        self.auc_threshold = auc_threshold
        self._predictions: deque = deque(maxlen=window)
        self._actuals: deque = deque(maxlen=window)
        self._drift_detected = False

    def update(self, predicted: float, actual: int) -> bool:
        """예측/실제 쌍 추가. 드리프트 감지 시 True 반환."""
        self._predictions.append(predicted)
        self._actuals.append(actual)

        if len(self._predictions) < self.window:
            return False

        auc = self._calc_auc()
        if auc is not None and auc < self.auc_threshold:
            if not self._drift_detected:
                log.warning(f"드리프트 감지: AUC={auc:.3f} < {self.auc_threshold} (최근 {self.window}건)")
                self._drift_detected = True
            return True

        self._drift_detected = False
        return False

    def _calc_auc(self) -> Optional[float]:
        """간단한 AUC 계산 (Mann-Whitney U statistic 기반)"""
        preds = np.array(self._predictions)
        acts = np.array(self._actuals)

        pos = preds[acts == 1]
        neg = preds[acts == 0]

        if len(pos) == 0 or len(neg) == 0:
            return None

        # Mann-Whitney U
        u = 0.0
        for p in pos:
            u += np.sum(p > neg) + 0.5 * np.sum(p == neg)

        auc = u / (len(pos) * len(neg))
        return auc

    @property
    def is_drift(self) -> bool:
        return self._drift_detected

    def reset(self):
        self._predictions.clear()
        self._actuals.clear()
        self._drift_detected = False
