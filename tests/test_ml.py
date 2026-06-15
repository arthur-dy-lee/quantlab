"""ML 测试（task #15）。build_dataset 纯逻辑必测；模型评估在装了 sklearn 时测。"""

from __future__ import annotations

import numpy as np
import pytest

from quantlab.ml.predictor import LogisticPredictor, build_dataset
from tests.conftest import ohlcv


def _series(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))))


def test_build_dataset_shapes():
    X, y = build_dataset(ohlcv(_series()), horizon=1)
    assert len(X) == len(y) and X.shape[1] >= 3
    assert set(int(v) for v in y.unique()) <= {0, 1}


def test_logistic_evaluate_reports_excess():
    pytest.importorskip("sklearn")
    X, y = build_dataset(ohlcv(_series()), horizon=1)
    rep = LogisticPredictor().evaluate(X, y, test_size=0.3)
    assert 0.0 <= rep["accuracy"] <= 1.0
    assert abs(rep["excess"] - (rep["accuracy"] - rep["baseline"])) < 1e-9
    assert rep["n_test"] > 0
