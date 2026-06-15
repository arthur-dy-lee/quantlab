"""编排层测试（task #6）—— 守住"本地优先 / 离线复现"不变量（用 FakeDataSource）。"""

from __future__ import annotations

import pandas as pd
import pytest

from quantlab.calendar import TradingCalendar
from quantlab.config import Config
from quantlab.data_manager import DataManager
from quantlab.datasources.base import DataSource, HistoryResult, Quote
from quantlab.enums import Market
from quantlab.errors import InsufficientData
from quantlab.storage.repository import BarRepository
from quantlab.symbols import Symbol


class FakeSource(DataSource):
    markets = [Market.US]
    name = "fake"

    def __init__(self):
        self.calls = 0

    def history(self, sym, start, end, freq):
        self.calls += 1
        end_day = TradingCalendar().last_trading_day(Market.US)
        idx = pd.bdate_range(end=pd.Timestamp(end_day), periods=10, name="date")
        closes = [float(x) for x in range(1, 11)]
        bars = pd.DataFrame(
            {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 1.0},
            index=idx,
        )
        return HistoryResult(bars, None)

    def quote(self, sym):  # pragma: no cover
        raise NotImplementedError


class FakeRegistry:
    def __init__(self, src):
        self.src = src

    def get_source(self, market):
        return self.src


def _dm(tmp_path, offline=False):
    src = FakeSource()
    cfg = Config(data_root=str(tmp_path), offline_only=offline)
    dm = DataManager(cfg, BarRepository(str(tmp_path)), FakeRegistry(src), TradingCalendar())
    return dm, src


def test_local_first_no_refetch(tmp_path):
    dm, src = _dm(tmp_path)
    dm.history("US:FAKE")
    assert src.calls == 1                 # 首次联网
    dm.history("US:FAKE")
    assert src.calls == 1                 # 本地新鲜 → 不再联网


def test_offline_never_fetches(tmp_path):
    dm, src = _dm(tmp_path, offline=True)
    with pytest.raises(InsufficientData):
        dm.history("US:FAKE")             # 离线且无本地 → 报错
    assert src.calls == 0                 # 绝不联网
