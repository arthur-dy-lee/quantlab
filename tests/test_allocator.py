"""加减仓决策层测试（合成数据，不联网）。

守住的不变量：区间打分单调于风险调整收益、最优区间重仓/最差区间轻仓、
仓位夹界、回测因果(无未来函数)、口径合理。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.signals import allocator as al
from quantlab.signals import thermometer as th
from quantlab.datasources import valuation_source as vs

P = dict(al.DEFAULT_PARAMS)


def _net(values, start="2008-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="B")
    net = pd.Series(np.asarray(values, float), index=idx, name="net")
    return pd.DataFrame({"top": 50 + net / 2, "bottom": 50 - net / 2, "net": net})


def _price(closes, start="2008-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="B")
    c = pd.Series(np.asarray(closes, float), index=idx)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c})


# ── 打分与映射 ────────────────────────────────────────────────────────────

def test_score_penalizes_tail():
    """同均值下，左尾更深 → 风险调整分更低。"""
    a = np.array([0.05, 0.05, 0.05, 0.05])             # 无尾
    b = np.array([0.10, 0.10, 0.10, -0.10])            # 同均值(0.05)但有 −10% 尾
    assert al._score(b, P["tail_k"]) < al._score(a, P["tail_k"])


def test_labels_band_and_direction():
    net = _net([-60, -30, 0, 30, 60] * 20)["net"]
    lab = al._labels(net, mom_window=5)
    assert set(lab["band"].dropna().unique()) <= set(al.NET_LABELS)
    assert set(lab["dir"].dropna().unique()) <= {"升温", "降温"}


# ── 区间表：仓位形状随数据 ────────────────────────────────────────────────

def test_regime_positions_follow_forward_returns():
    """构造"冷后涨、热后跌"的世界 → 冷档仓位 > 热档仓位（数据驱动，非先验）。"""
    rng = np.random.default_rng(0)
    n = 1200
    # 净温度在 ±60 间游走；价格"冷时未来涨、热时未来跌"
    net = pd.Series(60 * np.sin(np.linspace(0, 24, n)), name="net",
                    index=pd.bdate_range("2008-01-01", periods=n))
    drift = -net.shift(0).to_numpy() / 60 * 0.0015      # net 高→未来负漂移
    close = 100 * np.cumprod(1 + drift + rng.normal(0, 0.002, n))
    nt = pd.DataFrame({"top": 50 + net / 2, "bottom": 50 - net / 2, "net": net})
    price = _price(close, start="2008-01-01")
    table = al.regime_table(nt["net"], price, {**P, "min_samples": 20})
    cold = table[table["cell"].str.startswith("极冷")]["position"].mean()
    hot = table[table["cell"].str.startswith("极热")]["position"].mean()
    assert cold > hot                                   # 冷档(未来涨)重于热档(未来跌)


def test_positions_within_bounds():
    net = _net(list(np.linspace(-80, 80, 600)) * 2)["net"]
    price = _price(100 * (1 + 0.0002 * np.arange(1200)))
    table = al.regime_table(net, price, {**P, "min_samples": 20})
    assert table["position"].between(P["floor"], P["cap"]).all()


# ── 回测：因果 / 形状 ─────────────────────────────────────────────────────

def test_causal_positions_no_lookahead():
    """追加未来温度与价格，不得改写过去点的仓位。"""
    n = 700
    base_net = 50 * np.sin(np.linspace(0, 12, n))
    base_px = 100 * np.cumprod(1 + 0.0004 * np.cos(np.linspace(0, 12, n)))
    pp = {**P, "min_samples": 20}
    full = al.causal_positions(_net(np.r_[base_net, [90] * 80])["net"],
                               _price(np.r_[base_px, base_px[-1] * np.ones(80)]), pp)
    trunc = al.causal_positions(_net(base_net)["net"], _price(base_px), pp)
    assert np.allclose(full.iloc[:n].to_numpy(), trunc.to_numpy(), equal_nan=True)


def _patch(monkeypatch, net_df, price_df):
    monkeypatch.setattr(th, "net_temperature", lambda *a, **k: net_df, raising=True)
    monkeypatch.setattr(vs, "cn_index_ohlc", lambda *a, **k: price_df, raising=True)


def test_recommend_returns_valid_advice(monkeypatch):
    n = 800
    net_df = _net(40 * np.sin(np.linspace(0, 16, n)))
    price = _price(100 * np.cumprod(1 + 0.0004 * np.cos(np.linspace(0, 16, n))))
    _patch(monkeypatch, net_df, price)
    adv = al.recommend_position("CN", config_path=None)
    assert P["floor"] <= adv.target <= P["cap"]
    assert adv.band in al.NET_LABELS
    assert adv.turning in ("升温", "降温", "走平")
    assert adv.confidence in ("高", "中", "低")
    assert isinstance(adv.verdict, str) and adv.verdict


def test_backtest_shape_and_finite(monkeypatch):
    n = 1000
    net_df = _net(45 * np.sin(np.linspace(0, 20, n)))
    price = _price(100 * np.cumprod(1 + 0.0005 * np.cos(np.linspace(0, 20, n))))
    _patch(monkeypatch, net_df, price)
    eq, metrics = al.backtest_allocation("CN", config_path=None)
    assert {"strategy", "buy_hold", "position"} == set(eq.columns)
    assert len(eq) > 0 and np.isfinite(eq["strategy"].iloc[-1])
    assert eq["position"].between(0, 1).all()
    assert {"strat_cagr", "bh_cagr", "strat_maxdd", "strat_calmar", "avg_exposure"} <= set(metrics)
