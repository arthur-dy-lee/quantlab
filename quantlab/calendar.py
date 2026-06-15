"""交易日历（详细设计 §4.4）。

M1 用"工作日近似"（不含节假日表）——足够支撑新鲜度判断；
精确日历(exchange_calendars)与跨市场 align 留待 M2。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import pandas as pd

from quantlab.enums import Market


class TradingCalendar:
    def last_trading_day(self, market: Market, asof: date | None = None) -> date:
        d = asof or date.today()
        if market == Market.CRYPTO:
            return d
        while d.weekday() >= 5:  # 周六/日回退
            d -= timedelta(days=1)
        return d

    def is_trading_day(self, market: Market, d: date) -> bool:
        if market == Market.CRYPTO:
            return True
        return d.weekday() < 5

    def sessions(self, market: Market, start: date, end: date) -> pd.DatetimeIndex:
        freq = "D" if market == Market.CRYPTO else "B"
        return pd.date_range(start, end, freq=freq)

    def align(self, lead: Market, target: Market, lag: int = 1) -> Callable:
        raise NotImplementedError("TODO(M2): 跨市场 align")
