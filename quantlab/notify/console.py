"""控制台通知（默认通道）—— 直接打印格式化卡片。"""

from __future__ import annotations

from quantlab.notify.base import Notifier, SignalCard


class ConsoleNotifier(Notifier):
    def send(self, card: SignalCard) -> bool:
        lo, hi = card.ci
        print(
            f"[{card.kind.upper()}] {card.symbol}  条件={card.condition}\n"
            f"  上涨概率 {card.p_up:.1%}  基准 {card.base_rate:.1%}  edge {card.edge:+.1%}"
            f"  [95%CI {lo:.1%}~{hi:.1%}]\n"
            f"  样本 N={card.n}  建议仓位 {card.suggested_position:.0%}  MAE {card.risk_mae:.1%}"
            f"  @ {card.time:%Y-%m-%d %H:%M}"
        )
        return True
