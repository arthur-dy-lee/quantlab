"""测试公共工具。"""

from __future__ import annotations

import pandas as pd

from quantlab.constants import CLOSE, HIGH, LOW, OPEN, VOLUME


def ohlcv(closes, start="2024-01-01", highs=None, lows=None, volume=1.0):
    """用收盘价列表造一段合成 OHLCV（默认 OHLC 同值，便于断言）。"""
    idx = pd.date_range(start, periods=len(closes), freq="D", name="date")
    closes = [float(c) for c in closes]
    return pd.DataFrame(
        {
            OPEN: closes,
            HIGH: highs or closes,
            LOW: lows or closes,
            CLOSE: closes,
            VOLUME: float(volume),
        },
        index=idx,
    )
