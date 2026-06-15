"""回测测试（task #8）—— 守住"无未来函数"不变量。"""

from __future__ import annotations

import pandas as pd

from quantlab.backtest.engine import Backtester
from quantlab.backtest.strategies import Strategy
from tests.conftest import ohlcv


class _FixedStrategy(Strategy):
    def __init__(self, pos):
        self._pos = pos

    def generate_positions(self, df):
        return pd.Series(self._pos, index=df.index, dtype=float)


def test_no_lookahead():
    df = ohlcv([10, 11, 12, 13])
    # 策略在 idx0 就喊"持有"，但 idx1 的收益不应被计入（次日才生效）
    res = Backtester(cost_bps=0.0).run(df, _FixedStrategy([0, 1, 1, 1]))
    assert res.returns.iloc[0] == 0.0     # 首日无昨仓
    assert res.returns.iloc[1] == 0.0     # idx1 用的是 idx0 的仓位(=0) → 不偷看


def test_buy_hold_reference():
    df = ohlcv([10, 11, 12])
    res = Backtester(cost_bps=0.0).run(df, _FixedStrategy([1, 1, 1]))
    assert abs(res.buy_hold.iloc[-1] - 1.2) < 1e-9    # 10→12
