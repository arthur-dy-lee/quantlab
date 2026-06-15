"""通知出口（详细设计 §9）—— SignalCard / Notifier / NotifyLog / dispatch。"""

from __future__ import annotations

import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from quantlab.errors import NotifyError

log = logging.getLogger("quantlab")


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


class NotifyLog:
    """SQLite 跨进程去重（详细设计 §9）。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS notify_log "
                "(symbol TEXT, signal TEXT, sent_at TEXT, PRIMARY KEY(symbol, signal, sent_at))"
            )

    def should_send(self, card: SignalCard, window_min: int) -> bool:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT MAX(sent_at) FROM notify_log WHERE signal=?", (card.dedup_key,)
            ).fetchone()
        last = row[0] if row else None
        if not last:
            return True
        return datetime.now() - datetime.fromisoformat(last) >= timedelta(minutes=window_min)

    def record(self, card: SignalCard) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "INSERT OR REPLACE INTO notify_log VALUES (?,?,?)",
                (card.symbol, card.dedup_key, datetime.now().isoformat()),
            )


def dispatch(
    card: SignalCard,
    channels: list[str],
    notifiers: dict[str, Notifier],
    log_store: NotifyLog | None = None,
    throttle_minutes: int = 30,
) -> list[str]:
    """逐通道推送；按 dedup_key 在 throttle 窗口内去重；单通道失败不影响其它。"""
    if log_store is not None and not log_store.should_send(card, throttle_minutes):
        return []
    sent: list[str] = []
    for ch in channels:
        n = notifiers.get(ch)
        if n is None:
            log.warning("通知通道未配置: %s", ch)
            continue
        try:
            if n.send(card):
                sent.append(ch)
        except NotifyError as e:
            log.warning("通道 %s 推送失败: %s", ch, e)
    if sent and log_store is not None:
        log_store.record(card)
    return sent
