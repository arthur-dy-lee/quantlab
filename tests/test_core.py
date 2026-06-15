"""core 原语测试 —— 守住"无未来函数"不变量（详细设计 §14）。"""

from __future__ import annotations

import math

import pandas as pd

from quantlab.constants import CLOSE, HIGH, LOW, OPEN, VOLUME
from quantlab.core import forward_return, mae, shift_next_day, wilson_interval


def _df(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D", name="date")
    return pd.DataFrame(
        {OPEN: closes, HIGH: closes, LOW: closes, CLOSE: closes, VOLUME: 1.0}, index=idx
    )


def test_forward_return_no_lookahead():
    df = _df([1.0, 2.0, 3.0, 4.0])
    fwd = forward_return(df, n=1)
    assert fwd.iloc[0] == 1.0          # 2/1-1
    assert fwd.iloc[1] == 0.5          # 3/2-1
    assert abs(fwd.iloc[2] - (4 / 3 - 1)) < 1e-9
    assert math.isnan(fwd.iloc[3])     # 末行无未来 → NaN


def test_shift_next_day():
    pos = pd.Series([1.0, 1.0, 0.0])
    out = shift_next_day(pos)
    assert out.iloc[0] == 0.0          # 首日无昨日信号
    assert list(out.iloc[1:]) == [1.0, 1.0]


def test_mae_long():
    df = _df([10.0, 9.0, 11.0, 12.0])
    # t=0: 未来1根 low=9 → 9/10-1 = -0.1
    assert abs(mae(df, n=1).iloc[0] - (-0.1)) < 1e-9


def test_wilson_interval():
    lo, hi = wilson_interval(6, 10)
    assert 0.0 <= lo < 0.6 < hi <= 1.0
    assert wilson_interval(0, 0) == (math.nan, math.nan) or all(
        math.isnan(x) for x in wilson_interval(0, 0)
    )
