"""市场温度计合成逻辑测试（合成数据，不联网）。

守住的不变量：分位单调、顶/底方向互补、缺数据按剩余权重归一化、无未来函数。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.signals import thermometer as th


def _series(values, start="2020-01-01", name="x"):
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(np.asarray(values, float), index=idx, name=name)


# ── 单指标对齐 ────────────────────────────────────────────────────────────

def test_aligned_pct_top_bottom_complementary():
    """同一序列在 top/bottom 下温度分互补（和≈100）。"""
    s = _series(range(100))
    top = th._aligned_pct(s, "high", "top", winsor=0.0)
    bot = th._aligned_pct(s, "high", "bottom", winsor=0.0)
    assert np.allclose((top + bot).to_numpy(), 100.0)


def test_direction_high_vs_low_inverted():
    """递增序列：direction=high 顶部分接近 100；direction=low 顶部分接近 0。"""
    s = _series(range(200))
    hot_high = th._aligned_pct(s, "high", "top", winsor=0.0).iloc[-1]
    hot_low = th._aligned_pct(s, "low", "top", winsor=0.0).iloc[-1]
    assert hot_high > 95
    assert hot_low < 5


def test_winsorize_no_future_leak():
    """无未来函数：追加未来数据，不得改写过去点的裁剪结果。"""
    s = _series(list(range(50)) + [10_000] + list(range(50, 60)))
    full = th._winsorize_expanding(s, p=0.05)
    trunc = th._winsorize_expanding(s.iloc[:51], p=0.05)   # 截到异常值处
    # 过去点裁剪值与是否存在未来数据无关
    assert np.allclose(full.iloc[:51].to_numpy(), trunc.to_numpy())
    # 异常值确实被「过去」窗口裁掉
    assert full.iloc[50] < 1_000


# ── 合成与缺数据归一化 ────────────────────────────────────────────────────

def _patch_raw(monkeypatch, raws):
    monkeypatch.setattr(th, "_raw_indicators", lambda data_root, refresh: raws)


def test_compose_weighted_value(monkeypatch):
    """常数序列 → 各指标分位=100；按已知方向/权重得可预测温度（5 因子）。"""
    n = 60
    const = _series([5.0] * n)
    _patch_raw(monkeypatch, {k: const for k in
                             ("pe", "pb", "erp", "sentiment", "securitization")})
    out = th.compute_temperature("CN", "top", config_path=None)
    # 高方向(sec/sent/pe/pb)→hot 100；erp(低方向)→hot 0
    # top = (0.25+0.25+0.15+0.15)*100 + 0.20*0 = 80
    assert abs(out["temperature"].iloc[-1] - 80.0) < 1e-6


def test_missing_data_renormalizes(monkeypatch):
    """某指标早期缺失时，按剩余权重归一化，温度不为 NaN。"""
    n = 60
    const = _series([5.0] * n)
    short = _series([5.0] * 5, start="2020-02-25")    # 仅最后几天有 sentiment
    _patch_raw(monkeypatch, {"pe": const, "pb": const, "erp": const,
                             "securitization": const, "sentiment": short})
    out = th.compute_temperature("CN", "top", config_path=None)
    early = out["temperature"].iloc[0]
    # 早期无 sentiment：wsum=0.25(sec)+0.20(erp)+0.15(pe)+0.15(pb)=0.75
    # temp=(25+0+15+15)/0.75
    assert not np.isnan(early)
    assert abs(early - 55.0 / 0.75) < 1e-6


def test_net_temperature_sign(monkeypatch):
    """构造贵+拥挤的市场 → 顶部高、底部低、净为正。"""
    n = 80
    rising = _series(range(n))             # 估值/杠杆/证券化率单调走高
    _patch_raw(monkeypatch, {"pe": rising, "pb": rising, "securitization": rising,
                             "erp": _series(range(n, 0, -1)),  # ERP 走低=越来越贵
                             "sentiment": rising})
    nt = th.net_temperature("CN", config_path=None)
    last = nt.iloc[-1]
    assert last["top"] > last["bottom"]
    assert last["net"] > 0
