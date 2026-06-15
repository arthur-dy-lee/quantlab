"""飞书自定义机器人通知（详细设计 §9 / §13.4）。首选通道。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from quantlab.errors import NotifyError, SourceUnavailable
from quantlab.notify.base import Notifier, SignalCard

_TEMPLATE = {"buy": "red", "sell": "green", "warn": "orange"}


class FeishuNotifier(Notifier):
    def __init__(self, webhook: str, secret: str | None = None) -> None:
        self.webhook = webhook
        self.secret = secret

    def _sign(self, ts: int) -> str:
        s = f"{ts}\n{self.secret}"
        digest = hmac.new(s.encode("utf-8"), b"", hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _build_card(self, c: SignalCard) -> dict:
        lo, hi = c.ci
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": _TEMPLATE.get(c.kind, "blue"),
                "title": {"tag": "plain_text", "content": f"{c.kind.upper()} {c.symbol}"},
            },
            "elements": [
                {"tag": "div", "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**条件**\n{c.condition}"}},
                    {"is_short": True, "text": {"tag": "lark_md",
                        "content": f"**上涨概率**\n{c.p_up:.1%} (基准{c.base_rate:.1%}, edge {c.edge:+.1%})"}},
                    {"is_short": True, "text": {"tag": "lark_md",
                        "content": f"**样本/CI**\nN={c.n}, 95%CI {lo:.1%}~{hi:.1%}"}},
                    {"is_short": True, "text": {"tag": "lark_md",
                        "content": f"**建议仓位/风险**\n{c.suggested_position:.0%}, MAE {c.risk_mae:.1%}"}},
                ]},
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": f"仅供参考, 非投资建议 · {c.time:%Y-%m-%d %H:%M}"}]},
            ],
        }

    def send(self, card: SignalCard) -> bool:
        try:
            import requests
        except ImportError as e:
            raise SourceUnavailable("requests 未安装：pip install -e '.[notify]'") from e
        body: dict = {"msg_type": "interactive", "card": self._build_card(card)}
        if self.secret:
            ts = int(time.time())
            body |= {"timestamp": str(ts), "sign": self._sign(ts)}
        try:
            resp = requests.post(self.webhook, json=body, timeout=5)
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            raise NotifyError(f"飞书请求失败: {e}") from e
        if data.get("code", data.get("StatusCode", 0)) not in (0, None):
            raise NotifyError(f"飞书返回错误: {data}")
        return True
