"""因子 IC 加权测试（合成数据，不联网）。

守住的不变量：预测力强的因子权重高、PE/PB 共线均分、向等权收缩、无未来函数、缺数据归一化。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.core import forward_return
from quantlab.signals import factor_weights as fw


def _px(closes, start="2008-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="B")
    c = pd.Series(np.asarray(closes, float), index=idx)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c})


def _hot(erp_pred, n, seed=0, start="2008-01-01"):
    """erp 的 hot 分位与"未来收益"反相关(可预测)；pe/pb/sentiment 随机(IC≈0)。"""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="B")
    df = pd.DataFrame(index=idx)
    for k in ("pe", "pb", "erp", "sentiment"):
        df[k] = rng.uniform(0, 100, n)
    df["erp"] = erp_pred                    # 注入可预测的 erp hot
    df["pb"] = df["pe"] * 0.97 + rng.uniform(0, 3, n)   # pe/pb 强共线
    return df


def test_predictive_factor_gets_more_weight():
    """erp 强预测(hot 高→未来跌) → erp 权重显著高于无预测的 sentiment/pe。"""
    n = 600
    rng = np.random.default_rng(0)
    px = _px(100 * np.cumprod(1 + rng.normal(0, 0.01, n)))
    fwd = forward_return(px, 20)
    erp_hot = (100 - fwd.rank(pct=True) * 100).fillna(50).to_numpy()   # 与未来收益完全负相关
    hot = _hot(erp_hot, n)                    # pe/pb/sentiment 随机(IC≈0)
    w = fw.ic_weights(hot, px, horizon=20, shrink=0.5)
    assert w["erp"] > w["sentiment"]
    assert w["erp"] > w["pe"]


def test_pe_pb_share_valuation_equally():
    """PE/PB 合并为估值维度后均分 → 两者权重恒等。"""
    hot = _hot(np.random.default_rng(1).uniform(0, 100, 400), 400, seed=1)
    w = fw.ic_weights(hot, _px(100 * (1 + 0.0003 * np.arange(400))), horizon=20)
    assert abs(w["pe"] - w["pb"]) < 1e-12
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_shrink_to_equal_weight():
    """shrink=1 → 纯等权(3 维度各 1/3；pe=pb=1/6, erp=sentiment=1/3)。"""
    hot = _hot(np.linspace(0, 100, 500), 500, seed=2)
    w = fw.ic_weights(hot, _px(100 * (1 + 0.0004 * np.arange(500))), horizon=20, shrink=1.0)
    assert abs(w["erp"] - 1 / 3) < 1e-9
    assert abs(w["pe"] - 1 / 6) < 1e-9


def test_ic_weights_no_lookahead():
    """asof 截断：追加未来数据不改变历史时点的权重。"""
    n = 500
    erp = np.r_[np.linspace(0, 100, n), np.full(60, 95.0)]
    close = np.r_[100 * np.cumprod(1 + 0.0005 * np.cos(np.linspace(0, 20, n))),
                  np.full(60, 100.0)]
    hot = _hot(erp[:n], n, seed=3)
    hot_full = _hot(erp, n + 60, seed=3)
    hot_full.iloc[:n] = hot.values          # 前 n 行与 trunc 一致
    asof = hot.index[-1]
    w_trunc = fw.ic_weights(hot, _px(close[:n]), horizon=20, asof=asof)
    w_full = fw.ic_weights(hot_full, _px(close), horizon=20, asof=asof)
    for k in fw.FACTORS:
        assert abs(w_trunc[k] - w_full[k]) < 1e-9


def test_net_renormalizes_missing_factor():
    """某因子早期缺失(NaN) → 按可用权重归一化，net 非 NaN、在 [-100,100]。"""
    n = 200
    hot = _hot(np.linspace(0, 100, n), n, seed=4)
    hot.iloc[:50, hot.columns.get_loc("sentiment")] = np.nan   # 早期无两融
    w = {"pe": 0.25, "pb": 0.25, "erp": 0.25, "sentiment": 0.25}
    net = fw._net_from_weights(hot, w)
    assert net.notna().all()
    assert net.between(-100, 100).all()
    assert net.index.min() == hot.index.min()                  # 没丢早期
