"""选股筛选（详细设计 §8.4）—— 基本面规则对 ETF 跳过且不判负。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from quantlab.constants import CLOSE
from quantlab.enums import InstrumentType
from quantlab.indicators.technical import add_indicators
from quantlab.symbols import Symbol, infer_instrument_type

_ALL = {InstrumentType.STOCK, InstrumentType.ETF, InstrumentType.INDEX, InstrumentType.CRYPTO}


@dataclass
class Rule:
    name: str
    applicable_types: set[InstrumentType]
    fn: Callable[[pd.DataFrame], bool]


@dataclass
class ScreenHit:
    symbol: str
    matched: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _last(s: pd.Series) -> float:
    return float(s.iloc[-1])


# 默认技术面规则（对全类型适用）
DEFAULT_RULES: list[Rule] = [
    Rule("金叉(ma5>ma20)", _ALL, lambda d: _last(d["ma5"]) > _last(d["ma20"])),
    Rule("站上20日线", _ALL, lambda d: _last(d[CLOSE]) > _last(d["ma20"])),
]


class Screener:
    def __init__(self, dm) -> None:
        self.dm = dm

    def run(self, symbols: list[str], rules: list[Rule] | None = None) -> list[ScreenHit]:
        rules = rules or DEFAULT_RULES
        hits: list[ScreenHit] = []
        for s in symbols:
            sym = Symbol.parse(s)
            itype = infer_instrument_type(sym.market, sym.code)
            df = add_indicators(self.dm.history(s))
            matched, skipped, applicable = [], [], []
            for rule in rules:
                if itype not in rule.applicable_types:
                    skipped.append(rule.name)        # 不判负
                    continue
                applicable.append(rule.name)
                try:
                    if rule.fn(df):
                        matched.append(rule.name)
                except Exception:  # noqa: BLE001 —— 数据不足等，视为未命中
                    pass
            if applicable and len(matched) == len(applicable):
                hits.append(ScreenHit(sym.key, matched, skipped))
        return hits
