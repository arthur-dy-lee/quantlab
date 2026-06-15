"""邮件通知（SMTP，M3 通道）。最通用，实时性弱。"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from quantlab.errors import NotifyError
from quantlab.notify.base import Notifier, SignalCard


class EmailNotifier(Notifier):
    def __init__(self, host: str, port: int, user: str, password: str,
                 to: str, use_tls: bool = True) -> None:
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.to, self.use_tls = to, use_tls

    def send(self, card: SignalCard) -> bool:
        lo, hi = card.ci
        body = (
            f"{card.kind.upper()} {card.symbol}\n条件: {card.condition}\n"
            f"上涨概率 {card.p_up:.1%} (基准 {card.base_rate:.1%}, edge {card.edge:+.1%})\n"
            f"N={card.n}, 95%CI {lo:.1%}~{hi:.1%}\n"
            f"建议仓位 {card.suggested_position:.0%}, MAE {card.risk_mae:.1%}"
        )
        msg = MIMEText(body)
        msg["Subject"] = f"[QuantLab] {card.kind.upper()} {card.symbol}"
        msg["From"], msg["To"] = self.user, self.to
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as s:
                if self.use_tls:
                    s.starttls()
                s.login(self.user, self.password)
                s.send_message(msg)
        except Exception as e:  # noqa: BLE001
            raise NotifyError(f"邮件发送失败: {e}") from e
        return True
