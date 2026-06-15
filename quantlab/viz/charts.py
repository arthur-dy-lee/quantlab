"""图表（详细设计 §10.1）—— plotly 交互图。M2。

TODO(M2): plot_candles / plot_equity / plot_probability（懒加载 plotly）。
"""

from __future__ import annotations

import pandas as pd


def plot_candles(df: pd.DataFrame, indicators: list[str] | None = None):
    raise NotImplementedError("TODO(M2): plot_candles")


def plot_equity(result):
    raise NotImplementedError("TODO(M2): plot_equity")


def plot_probability(result):
    raise NotImplementedError("TODO(M2): plot_probability")
