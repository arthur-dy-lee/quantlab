"""按配置构造通知通道（详细设计 §9 / §14）。"""

from __future__ import annotations

from quantlab.config import Config
from quantlab.notify.base import Notifier
from quantlab.notify.console import ConsoleNotifier


def build_notifiers(cfg: Config) -> dict[str, Notifier]:
    notifiers: dict[str, Notifier] = {"console": ConsoleNotifier()}

    fc = cfg.notify.feishu or {}
    if fc.get("webhook"):
        from quantlab.notify.feishu import FeishuNotifier
        notifiers["feishu"] = FeishuNotifier(fc["webhook"], fc.get("secret") or None)

    tc = cfg.notify.telegram or {}
    if tc.get("token") and tc.get("chat_id"):
        from quantlab.notify.telegram import TelegramNotifier
        notifiers["telegram"] = TelegramNotifier(tc["token"], tc["chat_id"])

    ec = cfg.notify.email or {}
    if ec.get("host"):
        from quantlab.notify.email import EmailNotifier
        notifiers["email"] = EmailNotifier(**ec)

    return notifiers
