"""Symbol 解析与类型判定测试（详细设计 §4.2）。"""

from __future__ import annotations

import pytest

from quantlab.enums import InstrumentType, Market
from quantlab.errors import SymbolParseError
from quantlab.symbols import Symbol, infer_instrument_type


def test_parse_ok():
    s = Symbol.parse("CN:600519")
    assert s.market == Market.CN and s.code == "600519"
    assert s.key == "CN:600519"
    assert Symbol.parse("CRYPTO:BTC/USDT").code == "BTC/USDT"


def test_parse_bad():
    with pytest.raises(SymbolParseError):
        Symbol.parse("600519")          # 缺前缀
    with pytest.raises(SymbolParseError):
        Symbol.parse("XX:1")            # 未知市场


def test_infer_type():
    assert infer_instrument_type(Market.CN, "510050") == InstrumentType.ETF
    assert infer_instrument_type(Market.CN, "159819") == InstrumentType.ETF
    assert infer_instrument_type(Market.CN, "600519") == InstrumentType.STOCK
    assert infer_instrument_type(Market.US, "^IXIC") == InstrumentType.INDEX
    assert infer_instrument_type(Market.US, "QQQ", source_hint="ETF") == InstrumentType.ETF
    assert infer_instrument_type(Market.CRYPTO, "BTC/USDT") == InstrumentType.CRYPTO
