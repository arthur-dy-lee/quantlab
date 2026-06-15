"""通知测试（task #12）—— 守住"通知去重"不变量。"""

from __future__ import annotations

from datetime import datetime

from quantlab.notify.base import NotifyLog, Notifier, SignalCard, dispatch
from quantlab.notify.feishu import FeishuNotifier


def _card(symbol="CN:000300", kind="buy"):
    return SignalCard(
        symbol=symbol, condition="跌幅>1.5%", kind=kind, p_up=0.62, base_rate=0.53,
        edge=0.09, ci=(0.46, 0.75), n=42, suggested_position=0.3, risk_mae=-0.011,
        time=datetime(2026, 6, 15, 9, 30),
    )


class _Counter(Notifier):
    def __init__(self):
        self.sent = 0

    def send(self, card):
        self.sent += 1
        return True


def test_notifylog_dedup(tmp_path):
    log = NotifyLog(tmp_path / "q.db")
    c = _card()
    assert log.should_send(c, 30) is True
    log.record(c)
    assert log.should_send(c, 30) is False     # 窗口内不重复
    assert log.should_send(c, 0) is True        # 窗口=0 → 立即可再推


def test_dispatch_throttles(tmp_path):
    log = NotifyLog(tmp_path / "q.db")
    n = _Counter()
    notifiers = {"x": n}
    assert dispatch(_card(), ["x"], notifiers, log, throttle_minutes=30) == ["x"]
    assert n.sent == 1
    dispatch(_card(), ["x"], notifiers, log, throttle_minutes=30)  # 去重
    assert n.sent == 1


def test_feishu_card_shape():
    card = FeishuNotifier("http://x")._build_card(_card())
    assert card["header"]["template"] == "red"        # buy → red
    assert "elements" in card and len(card["elements"]) >= 1
