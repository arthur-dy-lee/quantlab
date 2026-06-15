"""盯盘信号触发层（详细设计 §8.5）—— 判定"当下条件成立"，再交 stats 标注。M2。

TODO(task #M2): SignalScanner.scan。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quantlab.stats.conditions import Condition


@dataclass
class SignalRule:
    name: str
    kind: str          # buy | sell
    cond: Condition


@dataclass
class Signal:
    symbol: str
    rule: SignalRule
    asof: datetime


class SignalScanner:
    def __init__(self, dm, rules: list[SignalRule]) -> None:
        self.dm = dm
        self.rules = rules

    def scan(self, watchlist: list[str]) -> list[Signal]:
        raise NotImplementedError("TODO(M2): SignalScanner.scan")
