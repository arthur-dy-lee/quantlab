"""存储层测试（task #4）—— 读写往返、合并去重、元数据。"""

from __future__ import annotations

from quantlab.enums import Freq, InstrumentType
from quantlab.storage.repository import BarRepository
from quantlab.symbols import Symbol
from tests.conftest import ohlcv


def test_roundtrip_and_meta(tmp_path):
    repo = BarRepository(str(tmp_path))
    sym = Symbol.parse("US:TEST").with_type(InstrumentType.STOCK)
    bars = ohlcv([10, 11, 12, 13, 14])
    repo.save(sym, Freq.DAY, bars, None, source="t")

    loaded = repo.load(sym, Freq.DAY)
    assert len(loaded) == 5
    assert list(loaded["close"]) == [10, 11, 12, 13, 14]

    m = repo.meta(sym, Freq.DAY)
    assert m.rows == 5 and m.instrument_type == "stock" and m.source == "t"
    assert len(repo.catalog()) == 1


def test_merge_dedup_keeps_last(tmp_path):
    repo = BarRepository(str(tmp_path))
    sym = Symbol.parse("US:TEST")
    repo.save(sym, Freq.DAY, ohlcv([1, 2, 3]), None)
    # 与第 3 天重叠，新值覆盖
    repo.save(sym, Freq.DAY, ohlcv([99, 100], start="2024-01-03"), None)
    out = repo.load(sym, Freq.DAY)
    assert len(out) == 4                       # 2024-01-01..04，无重复
    assert out["close"].loc["2024-01-03"] == 99
