"""飞书自定义机器人通知（详细设计 §9 / §13.4）。首选通道。

TODO(task #M2): _build_card（交互式卡片 JSON）+ send（加签 + POST）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from quantlab.notify.base import Notifier, SignalCard


class FeishuNotifier(Notifier):
    def __init__(self, webhook: str, secret: str | None = None) -> None:
        self.webhook = webhook
        self.secret = secret

    def _sign(self, ts: int) -> str:
        s = f"{ts}\n{self.secret}"
        digest = hmac.new(s.encode("utf-8"), b"", hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _build_card(self, card: SignalCard) -> dict:
        raise NotImplementedError("TODO(M2): FeishuNotifier._build_card")

    def send(self, card: SignalCard) -> bool:
        # body={"msg_type":"interactive","card":self._build_card(card)}; 加签; requests.post
        raise NotImplementedError("TODO(M2): FeishuNotifier.send")
