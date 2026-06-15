"""Telegram Bot 通知（M3 通道）。境内通常需代理。"""

from __future__ import annotations

from quantlab.errors import NotifyError, SourceUnavailable
from quantlab.notify.base import Notifier, SignalCard


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    def _text(self, c: SignalCard) -> str:
        lo, hi = c.ci
        return (
            f"[{c.kind.upper()}] {c.symbol}\n条件: {c.condition}\n"
            f"上涨概率 {c.p_up:.1%} (基准 {c.base_rate:.1%}, edge {c.edge:+.1%})\n"
            f"N={c.n}, 95%CI {lo:.1%}~{hi:.1%}\n"
            f"建议仓位 {c.suggested_position:.0%}, MAE {c.risk_mae:.1%}\n{c.time:%Y-%m-%d %H:%M}"
        )

    def send(self, card: SignalCard) -> bool:
        try:
            import requests
        except ImportError as e:
            raise SourceUnavailable("requests 未安装：pip install -e '.[notify]'") from e
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            resp = requests.post(url, json={"chat_id": self.chat_id, "text": self._text(card)}, timeout=5)
            if not resp.ok or not resp.json().get("ok"):
                raise NotifyError(f"telegram 返回错误: {resp.text}")
        except NotifyError:
            raise
        except Exception as e:  # noqa: BLE001
            raise NotifyError(f"telegram 请求失败: {e}") from e
        return True
