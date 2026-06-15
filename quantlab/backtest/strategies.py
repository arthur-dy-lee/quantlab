"""策略（详细设计 §8.2）—— 只产目标仓位 ∈ [0,1]，与引擎正交。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from quantlab.constants import CLOSE
from quantlab.indicators.technical import ma, rsi


class Strategy(ABC):
    @abstractmethod
    def generate_positions(self, df: pd.DataFrame) -> pd.Series:
        ...


class DualMAStrategy(Strategy):
    """快线在慢线上方 → 持有(1)，否则空仓(0)。"""

    def __init__(self, fast: int = 5, slow: int = 20) -> None:
        self.fast, self.slow = fast, slow

    def generate_positions(self, df: pd.DataFrame) -> pd.Series:
        fast = ma(df[CLOSE], self.fast)
        slow = ma(df[CLOSE], self.slow)
        return (fast > slow).astype(float)


class RsiReversionStrategy(Strategy):
    """RSI < low 入场(1)，RSI > high 出场(0)，其间持仓。"""

    def __init__(self, period: int = 2, low: float = 10, high: float = 90) -> None:
        self.period, self.low, self.high = period, low, high

    def generate_positions(self, df: pd.DataFrame) -> pd.Series:
        r = rsi(df[CLOSE], self.period)
        sig = pd.Series(np.nan, index=df.index)
        sig[r < self.low] = 1.0
        sig[r > self.high] = 0.0
        return sig.ffill().fillna(0.0)
