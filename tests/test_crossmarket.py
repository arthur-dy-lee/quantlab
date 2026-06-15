"""跨市场对齐测试（task #11）—— 守住"无前视"：lead day-T → target day-(T+1)。"""

from __future__ import annotations

from quantlab.calendar import TradingCalendar
from quantlab.stats.conditions import drop_gt
from quantlab.stats.crossmarket import _crossmarket_stats
from tests.conftest import ohlcv


def test_crossmarket_alignment_and_edge():
    # lead 在 idx1/3/5 下跌；target 在"被对齐到的次日"上涨
    lead = ohlcv([10, 8, 10, 8, 10, 8, 10])
    tgt = ohlcv([10, 10, 10, 12, 10, 12, 10])
    r = _crossmarket_stats(
        lead, tgt, drop_gt(0.0), forward=1,
        calendar=TradingCalendar(), lag=1, min_samples=1, name="x",
    )
    # lead 跌(idx1,3,5) → tgt idx2,4(idx6 的 fwd 为 NaN 被剔除) 命中
    assert r.n == 2
    assert r.p_up == 1.0
    assert abs(r.base_rate - (2 / 6)) < 1e-9
    assert abs(r.edge - (1.0 - 2 / 6)) < 1e-9


def test_align_series_lag1():
    cal = TradingCalendar()
    lead = ohlcv([1, 2, 3]).index
    tgt = ohlcv([1, 2, 3]).index
    s = cal.align_series(lead, tgt, lag=1)
    # target 第 1 天没有更早的 lead → NaT；第 2 天 → lead 第 1 天
    assert s.iloc[1] == lead[0]
    assert s.iloc[2] == lead[1]
