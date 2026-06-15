"""通知出口（详细设计 §9）—— SignalCard / Notifier / NotifyLog / dispatch。

TODO(task #M2): NotifyLog（SQLite 去重）与 dispatch。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SignalCard:
    symbol: str
    condition: str
    kind: str                      # buy | sell | warn
    p_up: float
    base_rate: float
    edge: float
    ci: tuple[float, float]
    n: int
    suggested_position: float
    risk_mae: float
    time: datetime
    extra: dict = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        return f"{self.symbol}|{self.condition}|{self.kind}"


class Notifier(ABC):
    @abstractmethod
    def send(self, card: SignalCard) -> bool:
        ...


# 通道名 → Notifier 实例
_REGISTRY: dict[str, Notifier] = {}


def register(name: str, notifier: Notifier) -> None:
    _REGISTRY[name] = notifier


class NotifyLog:
    """SQLite 跨进程去重（详细设计 §9）。"""

    def should_send(self, card: SignalCard, window_min: int) -> bool:
        raise NotImplementedError("TODO(M2): NotifyLog.should_send")

    def record(self, card: SignalCard) -> None:
        raise NotImplementedError("TODO(M2): NotifyLog.record")


def dispatch(card: SignalCard, channels: list[str], cfg) -> None:
    """逐通道：去重检查 → send → 记录；单通道失败不影响其它。"""
    raise NotImplementedError("TODO(M2): dispatch")
