"""可组合条件谓词（详细设计 §8.3）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from quantlab.constants import CLOSE, VOLUME
from quantlab.indicators.technical import rsi


@dataclass
class Condition:
    name: str
    fn: Callable[[pd.DataFrame], pd.Series]

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        return self.fn(df).reindex(df.index).fillna(False).astype(bool)

    def __and__(self, o: "Condition") -> "Condition":
        return Condition(f"({self.name} & {o.name})", lambda d: self(d) & o(d))

    def __or__(self, o: "Condition") -> "Condition":
        return Condition(f"({self.name} | {o.name})", lambda d: self(d) | o(d))

    def __invert__(self) -> "Condition":
        return Condition(f"~{self.name}", lambda d: ~self(d))


def drop_gt(pct: float) -> Condition:
    """单日跌幅 > pct（如 0.015 表示跌超 1.5%）。"""
    return Condition(f"跌幅>{pct:.1%}", lambda d: d[CLOSE].pct_change() < -abs(pct))


def n_down_days(n: int) -> Condition:
    """连续 n 天下跌。"""
    def fn(d: pd.DataFrame) -> pd.Series:
        down = (d[CLOSE].pct_change() < 0).astype(float)
        return down.rolling(n).sum() == n
    return Condition(f"连跌{n}天", fn)


def rsi_lt(t: float, n: int = 14) -> Condition:
    return Condition(f"RSI{n}<{t:g}", lambda d: rsi(d[CLOSE], n) < t)


def rsi_gt(t: float, n: int = 14) -> Condition:
    return Condition(f"RSI{n}>{t:g}", lambda d: rsi(d[CLOSE], n) > t)


def rise_gt(pct: float) -> Condition:
    """单日涨幅 > pct（如 0.02 表示涨超 2%）。"""
    return Condition(f"涨幅>{pct:.1%}", lambda d: d[CLOSE].pct_change() > abs(pct))


def vol_spike(k: float = 2.0) -> Condition:
    return Condition(f"放量>{k:g}x", lambda d: d[VOLUME] > k * d[VOLUME].rolling(20).mean())
