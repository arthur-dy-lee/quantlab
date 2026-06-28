"""温度计因子的 IC 加权（v1.1，A股）。见 research/温度计_加减仓决策_设计.md。

把温度计的因子权重从「拍脑袋」换成「按因子对指数未来收益的实际预测力(IC)」定，
并解决三个坑（见 research 实证 §）：

1. **共线性**：PE 与 PB 秩相关 0.92≈同一因子。故先合并成一个「估值」维度
   （IC 在合并维度上算、权重再均分给 PE/PB），避免重复计数。结果只剩 3 个正交维度：
   **估值(PE&PB) / ERP / 情绪(两融)**。
2. **过拟合**：|IC| 权重向**等权收缩**（shrink），噪声 IC 不至于把权重打飞。
3. **方向/符号**：只保留方向对的因子（hot 分位越高→未来越跌，即 IC<0）；IC≥0 的因子权重归 0。

口径：hot 分位=越贵/越热分越高（与 thermometer 同）；IC=hot 分位与指数未来 horizon 日收益的
秩相关（Spearman，无 scipy 用秩上皮尔逊）。**按指数各算一套**（IC 各指数不同，接可切换基准）。
**无未来函数**：`asof` 截断 + forward_return 末段自动 NaN→dropna，IC 只用已实现样本(s≤t−H)；
净温度时变权重按季度(rebalance_days)滚动重估。

净温度（单一权重集）：``net = Σ wᵢ·(2·hotᵢ − 100) / Σ wᵢ`` ∈ [−100, 100]。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.core import forward_return
from quantlab.datasources import valuation_source as vs
from quantlab.signals import thermometer as th

FACTORS = ["pe", "pb", "erp", "sentiment"]
GROUPS = ["valuation", "erp", "sentiment"]   # 3 正交维度（PE&PB 合并为 valuation）


def factor_hot_scores(data_root: str = "data/", refresh: bool = False,
                      winsor: float = 0.01) -> pd.DataFrame:
    """4 因子的 hot 分位(0–100，越贵/越热越高)。复用 thermometer 对齐逻辑，无未来函数。"""
    raw = th._raw_indicators(data_root, refresh)
    return pd.DataFrame(
        {k: th._aligned_pct(raw[k], th.DIRECTION[k], "top", winsor) for k in FACTORS}
    ).sort_index().ffill()


def _rank_ic(a: pd.Series, b: pd.Series, min_n: int = 60) -> float:
    """Spearman 秩相关（秩上的皮尔逊，免 scipy）。样本不足返回 NaN。"""
    m = a.notna() & b.notna()
    if int(m.sum()) < min_n:
        return float("nan")
    return float(a[m].rank().corr(b[m].rank()))


def factor_ic(hot: pd.DataFrame, price: pd.DataFrame, horizon: int = 60,
              asof: pd.Timestamp | None = None) -> dict[str, float]:
    """3 维度的前向 IC（valuation=PE&PB 合并）。asof 截断 → 只用已实现样本（因果）。"""
    px = price if asof is None else price[price.index <= asof]
    fwd = forward_return(px, horizon)
    d = hot.reindex(px.index).ffill()
    d = d.assign(fwd=fwd).dropna()
    if asof is not None:
        d = d[d.index <= asof]
    val = (d["pe"] + d["pb"]) / 2.0
    return {
        "valuation": _rank_ic(val, d["fwd"]),
        "erp": _rank_ic(d["erp"], d["fwd"]),
        "sentiment": _rank_ic(d["sentiment"], d["fwd"]),
    }


def ic_weights(hot: pd.DataFrame, price: pd.DataFrame, horizon: int = 60,
               shrink: float = 0.5, asof: pd.Timestamp | None = None) -> dict[str, float]:
    """4 因子(pe/pb/erp/sentiment)权重：3 维度按 |IC|(方向对) 定权 → 向等权收缩 → 估值均分给 PE/PB。

    - 方向对 = IC<0（越热未来越跌）；权重 ∝ max(0, −IC)。全不达标→等权。
    - shrink∈[0,1]：0=纯 IC，1=纯等权；默认 0.5 防过拟合。
    """
    gic = factor_ic(hot, price, horizon, asof)
    strength = {g: max(0.0, -(gic[g] if pd.notna(gic[g]) else 0.0)) for g in GROUPS}
    tot = sum(strength.values())
    w_ic = {g: (strength[g] / tot if tot > 0 else 1 / 3) for g in GROUPS}
    w = {g: (1 - shrink) * w_ic[g] + shrink * (1 / 3) for g in GROUPS}
    return {"pe": w["valuation"] / 2, "pb": w["valuation"] / 2,
            "erp": w["erp"], "sentiment": w["sentiment"]}


def _net_from_weights(hot: pd.DataFrame, weights: pd.DataFrame | dict) -> pd.Series:
    """净温度 = Σ wᵢ(2·hotᵢ−100)/Σwᵢ。weights 可为常量 dict 或时变 DataFrame(对齐 hot.index)。

    缺数据(NaN)的因子按**可用权重归一化**（同 thermometer hand 版），故两融未上线的
    早年(2010 前)仍用 PE/PB/ERP 算温度，不丢 2005–2009 历史。
    """
    if isinstance(weights, dict):
        weights = pd.DataFrame([weights] * len(hot), index=hot.index)
    h = hot.reindex(weights.index)
    contrib = pd.DataFrame({k: weights[k] * (2 * h[k] - 100) for k in FACTORS})
    avail_w = pd.DataFrame({k: weights[k].where(h[k].notna()) for k in FACTORS})
    num = contrib.sum(axis=1, min_count=1)
    den = avail_w.sum(axis=1).replace(0, np.nan)
    return (num / den).rename("net").dropna()


def ic_net_live(index_symbol: str = "000300", horizon: int = 60, shrink: float = 0.5,
                data_root: str = "data/", refresh: bool = False,
                winsor: float = 0.01) -> tuple[pd.Series, dict[str, float]]:
    """当下口径：全样本 IC 权重 + IC 加权净温度序列。返回 (net, weights)。"""
    hot = factor_hot_scores(data_root, refresh, winsor)
    price = vs.cn_index_ohlc(index_symbol, data_root, refresh)
    w = ic_weights(hot, price, horizon, shrink, asof=None)
    return _net_from_weights(hot, w), w


def ic_net_causal(index_symbol: str = "000300", horizon: int = 60, shrink: float = 0.5,
                  rebalance_days: int = 63, data_root: str = "data/", refresh: bool = False,
                  winsor: float = 0.01) -> pd.Series:
    """走查口径：按季度(rebalance_days)用扩张窗口 IC 重估权重，得因果 IC 加权净温度。无未来函数。"""
    hot = factor_hot_scores(data_root, refresh, winsor)
    price = vs.cn_index_ohlc(index_symbol, data_root, refresh)
    wts = pd.DataFrame(index=hot.index, columns=FACTORS, dtype=float)
    for t in hot.index[::rebalance_days]:
        wts.loc[t] = pd.Series(ic_weights(hot, price, horizon, shrink, asof=t))
    wts = wts.ffill().dropna()
    return _net_from_weights(hot, wts)
