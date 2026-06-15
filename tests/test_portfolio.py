"""组合回测测试（task #15）。"""

from __future__ import annotations

from quantlab.backtest.portfolio import PortfolioBacktester
from tests.conftest import ohlcv


def test_equal_weight_portfolio():
    a = ohlcv([10, 11, 12, 13, 14])      # 上行
    b = ohlcv([20, 19, 18, 17, 16])      # 下行
    res = PortfolioBacktester(cost_bps=0.0).run({"A": a, "B": b})
    assert len(res.equity_curve) == 5
    assert res.weights == {"A": 0.5, "B": 0.5}
    # 等权 A/B 的组合收益应落在两者之间
    ra = a["close"].iloc[-1] / a["close"].iloc[0] - 1
    rb = b["close"].iloc[-1] / b["close"].iloc[0] - 1
    assert min(ra, rb) <= res.total_return <= max(ra, rb)


def test_custom_weights_normalized():
    a = ohlcv([10, 11, 12])
    b = ohlcv([10, 10, 10])
    res = PortfolioBacktester(cost_bps=0.0).run({"A": a, "B": b}, weights={"A": 3, "B": 1})
    assert abs(res.weights["A"] - 0.75) < 1e-9 and abs(res.weights["B"] - 0.25) < 1e-9
