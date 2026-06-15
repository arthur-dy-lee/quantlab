"""盯盘 + 选股测试（task #13）—— ETF 对 stock-only 规则跳过且不判负。"""

from __future__ import annotations

from quantlab.calendar import TradingCalendar
from quantlab.config import Config
from quantlab.data_manager import DataManager
from quantlab.enums import Freq, InstrumentType
from quantlab.screener.screener import DEFAULT_RULES, Rule, Screener
from quantlab.signals.scanner import SignalRule, SignalScanner, annotate
from quantlab.stats.conditions import drop_gt
from quantlab.stats.sizing import FixedTierSizer
from quantlab.storage.repository import BarRepository
from quantlab.symbols import Symbol
from tests.conftest import ohlcv


def _dm(tmp_path, data: dict[str, list]) -> DataManager:
    repo = BarRepository(str(tmp_path))
    for s, closes in data.items():
        repo.save(Symbol.parse(s), Freq.DAY, ohlcv(closes), None, source="t")
    cfg = Config(data_root=str(tmp_path), offline_only=True)
    return DataManager(cfg, repo, None, TradingCalendar())


def test_screener_hit_and_etf_skip(tmp_path):
    up = list(range(1, 40))                          # 单调上行 → 技术规则全中
    dm = _dm(tmp_path, {"US:UP": up, "CN:510050": up})
    stock_only = Rule("仅个股", {InstrumentType.STOCK}, lambda d: True)
    hits = {h.symbol: h for h in Screener(dm).run(["US:UP", "CN:510050"], DEFAULT_RULES + [stock_only])}

    assert "US:UP" in hits and "CN:510050" in hits   # 两者都命中
    assert "仅个股" in hits["US:UP"].matched          # 个股：基本面规则参与
    assert "仅个股" in hits["CN:510050"].skipped       # ETF：基本面规则跳过(不判负)


def test_signals_scan_and_annotate(tmp_path):
    closes = [10, 9, 11, 9, 11, 9, 11, 9, 11, 9]      # 末日下跌
    dm = _dm(tmp_path, {"US:T": closes})
    rule = SignalRule("跌", "buy", drop_gt(0.0))
    sigs = SignalScanner(dm, [rule]).scan(["US:T"])
    assert len(sigs) == 1

    card = annotate(dm, sigs[0], forward=1, sizer=FixedTierSizer(), min_samples=1)
    assert card.symbol == "US:T" and card.kind == "buy"
    assert abs(card.edge - (card.p_up - card.base_rate)) < 1e-9
