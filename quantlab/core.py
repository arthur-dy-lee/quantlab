"""共享时序原语（详细设计 §4.5）—— ``stats`` 与 ``backtest`` 共用、共测。

**无未来函数**的唯一实现处：前向收益、次日生效。集中在此避免两处实现不一致。
"""

from __future__ import annotations

import math

import pandas as pd

from quantlab.constants import CLOSE, LOW


def forward_return(df: pd.DataFrame, n: int = 1, price: str = CLOSE) -> pd.Series:
    """``fwd[t] = price[t+n] / price[t] - 1``；末 ``n`` 行为 NaN（无未来数据）。"""
    if n < 1:
        raise ValueError("n 必须 >= 1")
    return df[price].shift(-n) / df[price] - 1.0


def mae(df: pd.DataFrame, n: int, side: str = "long") -> pd.Series:
    """最大不利波动：持有 ``[t+1, t+n]`` 期间相对 ``close[t]`` 的最不利幅度（≤0 做多）。"""
    if side != "long":
        raise NotImplementedError("当前仅支持 side='long'")
    # 未来 n 根的 low，对齐到 t
    shifted = pd.concat([df[LOW].shift(-k) for k in range(1, n + 1)], axis=1)
    worst_low = shifted.min(axis=1)
    return worst_low / df[CLOSE] - 1.0


def shift_next_day(positions: pd.Series) -> pd.Series:
    """信号次日生效（防未来函数）：仓位整体后移一根，首行补 0。"""
    return positions.shift(1).fillna(0.0)


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """二项比例 ``k/n`` 的 Wilson 置信区间（默认 95%）。``n==0`` 返回 (nan, nan)。"""
    if n <= 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))
