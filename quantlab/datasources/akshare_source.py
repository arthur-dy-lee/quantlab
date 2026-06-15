"""A股/港股数据源 akshare（详细设计 §5.4）。取**不复权**原始价。

复权事件(actions)拼装留待完善（TODO）：故 CN 当前 qfq/hfq 暂等同 raw，
复权正确性由合成数据 + yfinance actions 验证。
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from quantlab.datasources.base import DataSource, HistoryResult, Quote
from quantlab.enums import Freq, Market
from quantlab.errors import FetchError, SourceUnavailable
from quantlab.symbols import Symbol

_PERIOD = {Freq.DAY: "daily", Freq.WEEK: "weekly", Freq.MONTH: "monthly"}
_RENAME = {
    "日期": "date", "开盘": "open", "收盘": "close",
    "最高": "high", "最低": "low", "成交量": "volume",
}


class AkshareSource(DataSource):
    markets = [Market.CN, Market.HK]
    name = "akshare"

    def _ak(self):
        try:
            import akshare as ak
        except ImportError as e:
            raise SourceUnavailable("akshare 未安装：pip install -e '.[cn]'") from e
        return ak

    def history(self, sym: Symbol, start, end, freq: Freq) -> HistoryResult:
        ak = self._ak()
        if freq not in _PERIOD:
            raise FetchError(f"akshare 不支持周期 {freq}（A股仅日/周/月线）")
        fmt = lambda d: (d.strftime("%Y%m%d") if isinstance(d, date) else "19900101")  # noqa: E731
        try:
            raw = ak.stock_zh_a_hist(
                symbol=sym.code, period=_PERIOD[freq],
                start_date=fmt(start) if start else "19900101",
                end_date=fmt(end) if end else "22000101",
                adjust="",  # 不复权原始价
            )
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"akshare 取数失败 {sym.key}: {e}") from e
        if raw is None or raw.empty:
            raise FetchError(f"akshare 无数据: {sym.key}")
        bars = self._normalize(raw, rename=_RENAME)
        return HistoryResult(bars, actions=None)  # TODO: 拼装分红送配 → actions

    def quote(self, sym: Symbol) -> Quote:
        ak = self._ak()
        try:
            spot = ak.stock_zh_a_spot_em()  # 全市场快照（OPT-4：待缓存/批量）
            row = spot[spot["代码"] == sym.code]
            if row.empty:
                raise FetchError(f"akshare 快照无 {sym.key}")
            price = float(row.iloc[0]["最新价"])
            chg = float(row.iloc[0].get("涨跌幅", "nan")) / 100.0
        except FetchError:
            raise
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"akshare quote 失败 {sym.key}: {e}") from e
        return Quote(sym, price=price, time=datetime.now(), change_pct=chg, source=self.name)
