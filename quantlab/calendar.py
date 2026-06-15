"""交易日历（详细设计 §4.4）。

新鲜度判断用"工作日近似"（不含节假日表）；跨市场对齐用**数据驱动**的 ``align_series``
（merge_asof 真实交易日，无需节假日表）。精确日历(exchange_calendars) 留作可选增强。
"""

from __future__ import annotations

from datetime import date, timedelta

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

    def align_series(self, lead_index, target_index, lag: int = 1) -> pd.Series:
        """对每个 target 交易日，取其前 ``lag`` 个**已收盘**的 lead session 日期。

        用 merge_asof(direction=backward, 严格早于) 实现：lead day-T → target day-(T+1)，
        无前视（美股 T 收盘发生在 A股 T+1 开盘前）。返回 Series(target_date → lead_date)。
        """
        lead = pd.DatetimeIndex(lead_index).sort_values()
        tgt = pd.DatetimeIndex(target_index).sort_values()
        m = pd.merge_asof(
            pd.DataFrame({"t": tgt}),
            pd.DataFrame({"l": lead}),
            left_on="t", right_on="l",
            direction="backward", allow_exact_matches=False,
        )
        s = pd.Series(m["l"].values, index=pd.DatetimeIndex(m["t"].values))
        if lag > 1:
            pos = {d: i for i, d in enumerate(lead)}

            def back(d):
                if pd.isna(d):
                    return pd.NaT
                i = pos.get(pd.Timestamp(d))
                j = (i - (lag - 1)) if i is not None else None
                return lead[j] if (j is not None and j >= 0) else pd.NaT

            s = s.map(back)
        return s
