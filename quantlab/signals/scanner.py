"""盯盘信号触发层（详细设计 §8.5）—— 判定"当下条件成立"，再交 stats 标注成卡片。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quantlab.indicators.technical import add_indicators
from quantlab.notify.base import SignalCard
from quantlab.stats.conditions import Condition, drop_gt, n_down_days, rsi_lt
from quantlab.stats.probability import probability
from quantlab.stats.sizing import PositionSizer


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


DEFAULT_RULES: list[SignalRule] = [
    SignalRule("超卖反弹", "buy", rsi_lt(30)),
    SignalRule("连跌企稳", "buy", drop_gt(0.015) & n_down_days(2)),
]


class SignalScanner:
    """实时触发层。"""

    def __init__(self, dm, rules: list[SignalRule] | None = None) -> None:
        self.dm = dm
        self.rules = rules or DEFAULT_RULES

    def scan(self, watchlist: list[str]) -> list[Signal]:
        out: list[Signal] = []
        for sym in watchlist:
            df = add_indicators(self.dm.history(sym))
            if df.empty:
                continue
            for rule in self.rules:
                if bool(rule.cond(df).iloc[-1]):
                    out.append(Signal(sym, rule, df.index[-1].to_pydatetime()))
        return out


def annotate(
    dm,
    signal: Signal,
    forward: int = 1,
    sizer: PositionSizer | None = None,
    min_samples: int = 30,
) -> SignalCard:
    """标注层：用历史概率/edge/仓位/风险，把 Signal 组成可推送的 SignalCard。"""
    df = add_indicators(dm.history(signal.symbol))
    r = probability(df, signal.rule.cond, forward, min_samples, signal.symbol)
    pos = sizer.size(r) if sizer else 0.0
    return SignalCard(
        symbol=signal.symbol, condition=r.condition, kind=signal.rule.kind,
        p_up=r.p_up, base_rate=r.base_rate, edge=r.edge, ci=(r.ci_low, r.ci_high),
        n=r.n, suggested_position=pos, risk_mae=r.mae, time=datetime.now(),
    )
