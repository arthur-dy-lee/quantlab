"""ML 预测扩展位（详细设计 §8.6）。M3。

TODO(M3): 历史指标做特征预测下一根涨跌；诚实评估(报相对多数类基准的超额)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Predictor(ABC):
    @abstractmethod
    def fit(self, X, y) -> None: ...

    @abstractmethod
    def predict(self, X) -> pd.Series: ...

    @abstractmethod
    def evaluate(self, X, y) -> dict: ...
