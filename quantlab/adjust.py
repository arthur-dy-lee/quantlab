"""复权（详细设计 §7.1）—— 缓存只存原始价 + 事件，读取时按需现算（纯函数）。

因子方法：每个除权除息日 t 的"价格下跌比" r_t = (C_prev - D)/C_prev · (1/拆股k)。
后复权因子 hfq_af[t] = ∏_{s<=t} (1/r_s)（早期≈1，往后累乘）。
前复权 qfq_af[t] = hfq_af[t] / hfq_af[-1]（最新=1 → 最新价≈原始价）。
"""

from __future__ import annotations

import pandas as pd

from quantlab.constants import CLOSE, PRICE_COLS
from quantlab.enums import Adjust


def compute_factors(actions: pd.DataFrame | None, raw: pd.DataFrame) -> pd.Series:
    """分红/拆股事件 → 后复权因子 ``hfq_af``（对齐到 ``raw.index``）。无事件则全 1。"""
    af = pd.Series(1.0, index=raw.index)
    if actions is None or actions.empty:
        return af
    prev_close = raw[CLOSE].shift(1)
    r = pd.Series(1.0, index=raw.index)
    for t in actions.index:
        if t not in raw.index:
            continue
        cp = prev_close.get(t)
        if cp is None or pd.isna(cp) or cp <= 0:
            continue
        ratio = 1.0
        div = float(actions.get("dividend", pd.Series()).get(t, 0.0) or 0.0)
        split = float(actions.get("split", pd.Series()).get(t, 0.0) or 0.0)
        if div:
            ratio *= (cp - div) / cp
        if split and split > 0:
            ratio *= 1.0 / split
        r[t] = ratio
    return (1.0 / r).cumprod()


def apply(raw: pd.DataFrame, hfq_af: pd.Series | None, mode: Adjust) -> pd.DataFrame:
    """按 ``mode`` 现算复权价（纯函数，不改缓存）。"""
    if mode == Adjust.RAW or hfq_af is None:
        return raw
    af = hfq_af.reindex(raw.index).ffill().fillna(1.0)
    if mode == Adjust.QFQ:
        last = af.iloc[-1]
        if last and last != 0:
            af = af / last
    out = raw.copy()
    for col in PRICE_COLS:
        if col in out.columns:
            out[col] = raw[col] * af
    return out
