"""编排层门面 DataManager（详细设计 §7.2）—— 上层唯一取数入口。"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from quantlab import adjust as adjust_mod
from quantlab.calendar import TradingCalendar
from quantlab.config import Config
from quantlab.constants import CLOSE, HIGH, LOW, OPEN, VOLUME
from quantlab.datasources.base import Quote
from quantlab.datasources.registry import SourceRegistry
from quantlab.enums import Adjust, Freq, Market
from quantlab.errors import InsufficientData
from quantlab.retry import with_retry
from quantlab.storage.repository import BarMeta, BarRepository
from quantlab.symbols import Symbol, infer_instrument_type

log = logging.getLogger("quantlab")

_RESAMPLE = {Freq.WEEK: "W", Freq.MONTH: "ME"}


class DataManager:
    def __init__(
        self,
        config: Config,
        repo: BarRepository,
        registry: SourceRegistry,
        calendar: TradingCalendar,
    ) -> None:
        self.cfg = config
        self.repo = repo
        self.registry = registry
        self.calendar = calendar

    # ---- public ----
    def history(
        self,
        symbol: "str | Symbol",
        start: "str | date | None" = None,
        end: "str | date | None" = None,
        freq: Freq = Freq.DAY,
        adjust: Adjust | None = None,
    ) -> pd.DataFrame:
        sym = Symbol.parse(symbol)
        adjust = adjust or self.cfg.adjust_default
        start_d, end_d = _to_date(start), _to_date(end)

        # 周/月线：以日线为唯一真相，本地重采样
        fetch_freq = Freq.DAY if freq in _RESAMPLE else freq

        meta = self.repo.meta(sym, fetch_freq)
        if not self.cfg.offline_only and self._needs_fetch(meta, start_d, sym.market):
            self._fetch_and_save(sym, start_d, end_d, fetch_freq)

        raw = self.repo.load(sym, fetch_freq)
        if raw.empty:
            raise InsufficientData(f"本地无数据且未取到: {sym.key}")

        if freq in _RESAMPLE:
            raw = _resample(raw, _RESAMPLE[freq])

        out = self._adjust(sym, raw, adjust)
        return _slice(out, start_d, end_d)

    def quote(self, symbol: "str | Symbol") -> Quote:
        sym = Symbol.parse(symbol)
        if self.cfg.offline_only:
            local = self.repo.load(sym, Freq.DAY)
            if local.empty:
                raise InsufficientData(f"离线且本地无数据: {sym.key}")
            last = local.iloc[-1]
            return Quote(sym, price=float(last[CLOSE]), time=local.index[-1].to_pydatetime(),
                         source="local", note="offline: 最近本地收盘")
        return self.registry.get_source(sym.market).quote(sym)

    def download(self, symbols: list[str], start=None, end=None, freq: Freq = Freq.DAY) -> list[BarMeta]:
        out: list[BarMeta] = []
        for s in symbols:
            try:
                self.history(s, start, end, freq)
                m = self.repo.meta(Symbol.parse(s), Freq.DAY if freq in _RESAMPLE else freq)
                if m:
                    out.append(m)
            except Exception as e:  # noqa: BLE001 —— 单标的失败不中断批量
                log.warning("download 失败 %s: %s", s, e)
        return out

    def catalog(self) -> list[BarMeta]:
        return self.repo.catalog()

    # ---- internal ----
    def _needs_fetch(self, meta: BarMeta | None, start: date | None, market: Market) -> bool:
        if meta is None:
            return True
        if start and meta.start > start:
            return True
        if meta.end < self.calendar.last_trading_day(market):
            return True
        return False

    def _fetch_and_save(self, sym: Symbol, start, end, freq: Freq) -> None:
        src = self.registry.get_source(sym.market)
        res = with_retry(lambda: src.history(sym, start, end, freq),
                         **{k: self.cfg.retry[k] for k in ("retries", "backoff") if k in self.cfg.retry})
        typed = sym.with_type(infer_instrument_type(sym.market, sym.code))
        self.repo.save(typed, freq, res.bars, res.actions, source=src.name)

    def _adjust(self, sym: Symbol, raw: pd.DataFrame, adjust: Adjust) -> pd.DataFrame:
        if sym.market == Market.CRYPTO or adjust == Adjust.RAW:
            return raw
        actions = self.repo.load_factors(sym)
        hfq_af = adjust_mod.compute_factors(actions, raw)
        return adjust_mod.apply(raw, hfq_af, adjust)


def _to_date(d) -> date | None:
    if d is None or isinstance(d, date):
        return d
    return pd.Timestamp(d).date()


def _slice(df: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    return df


def _resample(raw: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {OPEN: "first", HIGH: "max", LOW: "min", CLOSE: "last", VOLUME: "sum"}
    cols = [c for c in agg if c in raw.columns]
    return raw.resample(rule).agg({c: agg[c] for c in cols}).dropna(how="any")
