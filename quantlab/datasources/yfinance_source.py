"""美股/港股数据源 yfinance（详细设计 §5.4）。第三方库懒加载。"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from quantlab.datasources.base import DataSource, HistoryResult, Quote
from quantlab.enums import Freq, Market
from quantlab.errors import FetchError, SourceUnavailable
from quantlab.symbols import Symbol

_INTERVAL = {Freq.DAY: "1d", Freq.WEEK: "1wk", Freq.MONTH: "1mo", Freq.HOUR: "1h", Freq.MIN: "1m"}


class YFinanceSource(DataSource):
    markets = [Market.US, Market.HK]
    name = "yfinance"

    def _yf(self):
        try:
            import yfinance as yf
        except ImportError as e:
            raise SourceUnavailable("yfinance 未安装：pip install -e '.[us]'") from e
        return yf

    def history(self, sym: Symbol, start, end, freq: Freq) -> HistoryResult:
        yf = self._yf()
        try:
            t = yf.Ticker(sym.code)
            raw = t.history(
                start=start, end=end, interval=_INTERVAL.get(freq, "1d"),
                auto_adjust=False, actions=True,
            )
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"yfinance 取数失败 {sym.key}: {e}") from e
        if raw is None or raw.empty:
            raise FetchError(f"yfinance 无数据: {sym.key}")
        bars = self._normalize(raw)
        actions = self._extract_actions(raw)
        return HistoryResult(bars, actions)

    @staticmethod
    def _extract_actions(raw: pd.DataFrame) -> pd.DataFrame | None:
        cols = {c.lower(): c for c in raw.columns}
        div = raw[cols["dividends"]] if "dividends" in cols else None
        spl = raw[cols["stock splits"]] if "stock splits" in cols else None
        if div is None and spl is None:
            return None
        ev = pd.DataFrame(
            {
                "dividend": div if div is not None else 0.0,
                "split": spl if spl is not None else 0.0,
            }
        )
        ev.index = pd.DatetimeIndex(pd.to_datetime(ev.index)).tz_localize(None)
        ev = ev[(ev["dividend"] > 0) | (ev["split"] > 0)]
        return ev if not ev.empty else None

    def quote(self, sym: Symbol) -> Quote:
        yf = self._yf()
        try:
            fi = yf.Ticker(sym.code).fast_info
            price = float(fi["last_price"])
            prev = float(fi.get("previous_close")) if fi.get("previous_close") else None
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"yfinance quote 失败 {sym.key}: {e}") from e
        chg = (price / prev - 1.0) if prev else None
        return Quote(sym, price=price, time=datetime.now(), prev_close=prev,
                     change_pct=chg, source=self.name)
