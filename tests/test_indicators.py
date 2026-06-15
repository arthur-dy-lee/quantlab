"""指标测试（task #7）。"""

from __future__ import annotations

import math

from quantlab.constants import DEFAULT_INDICATORS, OHLCV
from quantlab.indicators.technical import add_indicators, ma, rsi
from tests.conftest import ohlcv


def test_ma():
    df = ohlcv([1, 2, 3])
    out = ma(df["close"], 2)
    assert math.isnan(out.iloc[0])
    assert out.iloc[1] == 1.5 and out.iloc[2] == 2.5


def test_rsi_range():
    df = ohlcv(list(range(1, 30)))      # 单调上行
    r = rsi(df["close"], 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()
    assert r.iloc[-1] > 90              # 持续上涨 → RSI 高


def test_add_indicators_adds_and_preserves():
    df = ohlcv(list(range(1, 40)))
    out = add_indicators(df)
    for col in DEFAULT_INDICATORS:
        assert col in out.columns
    assert list(df.columns) == OHLCV    # 原 df 未被改
