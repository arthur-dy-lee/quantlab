"""选股筛选（详细设计 §8.4）—— 基本面规则对 ETF 跳过且不判负。M2。

TODO(task #M2): Screener.run。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from quantlab.enums import InstrumentType


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


class Screener:
    def __init__(self, dm) -> None:
        self.dm = dm

    def run(self, symbols: list[str], rules: list[Rule]) -> list[ScreenHit]:
        raise NotImplementedError("TODO(M2): Screener.run")
