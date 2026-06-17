"""curated 清单（美股/加密）的健全性测试。

不联网：只校验清单能解析成合法 Symbol、市场/类型判定正确、无重复。
"""

from __future__ import annotations

from quantlab.enums import InstrumentType, Market
from quantlab.symbols import Symbol, infer_instrument_type
from quantlab.universe import (
    CRYPTO_TOP10,
    US_INDEXES,
    US_MEGACAP_TECH,
    US_TECH_AI_ETFS,
    list_crypto_symbols,
    list_us_symbols,
)


def test_us_list_parses_and_is_us():
    syms = list_us_symbols()
    assert all(Symbol.parse(s).market == Market.US for s in syms)
    # 七姐妹 + 2 个纳指 + 8 个 ETF，且无重复
    assert len(syms) == len(US_MEGACAP_TECH) + len(US_INDEXES) + len(US_TECH_AI_ETFS)
    assert len(set(syms)) == len(syms)
    assert "US:AAPL" in syms and "US:TSLA" in syms


def test_us_indexes_inferred_as_index():
    for code in US_INDEXES:
        assert infer_instrument_type(Market.US, code) == InstrumentType.INDEX


def test_crypto_list_top10_parses():
    syms = list_crypto_symbols()
    assert len(syms) == 10 and len(set(syms)) == 10
    for s in syms:
        sym = Symbol.parse(s)
        assert sym.market == Market.CRYPTO
        assert infer_instrument_type(sym.market, sym.code) == InstrumentType.CRYPTO
    # 主流币种在列、排除稳定币（USDT/USDC 不作为标的）
    assert "CRYPTO:BTC/USDT" in syms and "CRYPTO:ETH/USDT" in syms
    bases = {p.split("/")[0] for p in CRYPTO_TOP10}
    assert not ({"USDT", "USDC", "DAI"} & bases)
