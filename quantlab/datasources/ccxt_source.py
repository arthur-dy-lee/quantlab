"""加密货币数据源 ccxt（详细设计 §5.4）。无复权（actions=None）。"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from quantlab.constants import CLOSE, DATE, HIGH, LOW, OPEN, VOLUME
from quantlab.datasources.base import DataSource, HistoryResult, Quote
from quantlab.enums import Freq, Market
from quantlab.errors import FetchError, SourceUnavailable
from quantlab.symbols import Symbol

_TF = {Freq.DAY: "1d", Freq.WEEK: "1w", Freq.MONTH: "1M", Freq.HOUR: "1h", Freq.MIN: "1m"}


class CcxtSource(DataSource):
    markets = [Market.CRYPTO]
    name = "ccxt"

    def __init__(self, exchange: str = "kraken") -> None:
        self.exchange = exchange

    def _client(self):
        try:
            import ccxt
        except ImportError as e:
            raise SourceUnavailable("ccxt 未安装：pip install -e '.[crypto]'") from e
        try:
            return getattr(ccxt, self.exchange)()
        except AttributeError as e:
            raise SourceUnavailable(f"ccxt 无交易所 {self.exchange}") from e

    def history(self, sym: Symbol, start, end, freq: Freq) -> HistoryResult:
        ex = self._client()
        since = int(datetime(start.year, start.month, start.day).timestamp() * 1000) if isinstance(start, date) else None
        try:
            rows = ex.fetch_ohlcv(sym.code, timeframe=_TF.get(freq, "1d"), since=since, limit=1000)
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"ccxt 取数失败 {sym.key}: {e}") from e
        if not rows:
            raise FetchError(f"ccxt 无数据: {sym.key}")
        df = pd.DataFrame(rows, columns=["ts", OPEN, HIGH, LOW, CLOSE, VOLUME])
        df[DATE] = pd.to_datetime(df["ts"], unit="ms")
        bars = self._normalize(df.drop(columns="ts"))
        return HistoryResult(bars, actions=None)

    def quote(self, sym: Symbol) -> Quote:
        ex = self._client()
        try:
            t = ex.fetch_ticker(sym.code)
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"ccxt quote 失败 {sym.key}: {e}") from e
        return Quote(sym, price=float(t["last"]), time=datetime.now(),
                     change_pct=(t.get("percentage") or 0) / 100.0, source=self.name)
