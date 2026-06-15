"""ML 预测（详细设计 §8.6）—— 历史指标做特征，预测下一根涨跌；诚实评估。

诚实评估：时序切分(不打乱)，报相对**多数类基准**的超额，而非只看准确率。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from quantlab.constants import CLOSE
from quantlab.core import forward_return
from quantlab.errors import InsufficientData, SourceUnavailable
from quantlab.indicators.technical import add_indicators

_FEATURES = ["rsi14", "macd_hist", "atr14", "ret1", "ret5"]


def build_dataset(df: pd.DataFrame, horizon: int = 1) -> tuple[pd.DataFrame, pd.Series]:
    """OHLCV → (特征 X, 标签 y=未来 horizon 根涨=1)。"""
    d = add_indicators(df)
    d = d.assign(ret1=d[CLOSE].pct_change(), ret5=d[CLOSE].pct_change(5))
    feats = [c for c in _FEATURES if c in d.columns]
    y = (forward_return(d, horizon) > 0).astype(int)
    data = d[feats].join(y.rename("y")).replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < 30:
        raise InsufficientData("样本不足以训练")
    return data[feats], data["y"]


class Predictor(ABC):
    @abstractmethod
    def fit(self, X, y): ...

    @abstractmethod
    def predict(self, X) -> pd.Series: ...

    def evaluate(self, X: pd.DataFrame, y: pd.Series, test_size: float = 0.3) -> dict:
        """时序切分 → 训练/测试；报准确率、多数类基准、超额。"""
        n = len(X)
        split = int(n * (1 - test_size))
        Xtr, Xte = X.iloc[:split], X.iloc[split:]
        ytr, yte = y.iloc[:split], y.iloc[split:]
        if len(Xte) < 5 or ytr.nunique() < 2:
            raise InsufficientData("训练/测试样本不足或单一类别")
        self.fit(Xtr, ytr)
        pred = np.asarray(self.predict(Xte))
        acc = float((pred == yte.values).mean())
        base = float(max(yte.mean(), 1 - yte.mean()))   # 多数类基准
        return {"accuracy": acc, "baseline": base, "excess": acc - base, "n_test": int(len(yte))}


class LogisticPredictor(Predictor):
    def __init__(self) -> None:
        self._pipe = None

    def fit(self, X, y):
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError as e:
            raise SourceUnavailable("scikit-learn 未安装：pip install -e '.[ml]'") from e
        self._pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
        self._pipe.fit(X, y)
        return self

    def predict(self, X) -> pd.Series:
        return pd.Series(self._pipe.predict(X), index=X.index)
