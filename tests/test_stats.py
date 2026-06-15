"""统计概率 + 仓位测试（task #9）—— 守住"edge 透明 / 无优势不建仓"。"""

from __future__ import annotations

from quantlab.stats.conditions import drop_gt
from quantlab.stats.probability import ProbabilityResult, probability
from quantlab.stats.sizing import FixedTierSizer, KellyConservativeSizer
from tests.conftest import ohlcv


def test_probability_edge_and_baserate():
    # 每个下跌日的次日都上涨 → 条件概率 1.0，基准率 0.5
    df = ohlcv([10, 9, 11, 9, 11, 9, 11])
    r = probability(df, drop_gt(0.0), forward=1, min_samples=1)
    assert r.n == 3
    assert r.p_up == 1.0
    assert abs(r.base_rate - 0.5) < 1e-9
    assert abs(r.edge - 0.5) < 1e-9
    assert abs(r.edge - (r.p_up - r.base_rate)) < 1e-9
    assert r.reliable is True


def _mk(p_up, edge, reliable=True, payoff=1.5):
    return ProbabilityResult(
        condition="c", symbol="X", forward=1, n=50, p_up=p_up, base_rate=p_up - edge,
        edge=edge, ci_low=0.0, ci_high=1.0, mean_ret=0.01, median_ret=0.01,
        payoff=payoff, mae=-0.01, reliable=reliable,
    )


def test_fixed_tier_sizer():
    assert FixedTierSizer(0.5).size(_mk(0.72, 0.1)) == 0.5
    assert FixedTierSizer(0.5).size(_mk(0.62, 0.05)) == 0.1


def test_sizer_no_edge_or_unreliable_returns_zero():
    assert FixedTierSizer().size(_mk(0.8, -0.01)) == 0.0          # edge<=0
    assert FixedTierSizer().size(_mk(0.8, 0.2, reliable=False)) == 0.0
    assert KellyConservativeSizer().size(_mk(0.8, -0.01)) == 0.0


def test_kelly_within_bounds():
    s = KellyConservativeSizer(max_position=0.5, kelly_fraction=0.3).size(_mk(0.7, 0.15, payoff=2.0))
    assert 0.0 <= s <= 0.5
