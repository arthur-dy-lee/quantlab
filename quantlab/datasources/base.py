"""数据源抽象与契约（详细设计 §5.1–5.3）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

import pandas as pd

from quantlab.constants import DATE, HIGH, LOW, OHLCV
from quantlab.enums import Freq, Market
from quantlab.errors import DataQualityError
from quantlab.symbols import Symbol


@dataclass
class Quote:
    symbol: Symbol
    price: float
    time: datetime
    prev_close: float | None = None
    change_pct: float | None = None
    source: str = ""
    note: str = ""


@dataclass
class HistoryResult:
    bars: pd.DataFrame                    # 标准 OHLCV（原始价）
    actions: pd.DataFrame | None = None   # index=date, cols=[dividend, split]; 无则 None


class DataSource(ABC):
    markets: ClassVar[list[Market]] = []
    name: ClassVar[str] = "base"

    @abstractmethod
    def history(self, sym: Symbol, start: date | None, end: date | None, freq: Freq) -> HistoryResult:
        ...

    @abstractmethod
    def quote(self, sym: Symbol) -> Quote:
        ...

    def _normalize(self, raw: pd.DataFrame, rename: dict | None = None) -> pd.DataFrame:
        """归一 + 校验/清洗 → 标准 OHLCV（详细设计 §5.3）。"""
        df = raw.copy()
        if rename:
            df = df.rename(columns=rename)
        df.columns = [str(c).strip().lower() for c in df.columns]

        if DATE in df.columns:
            df = df.set_index(DATE)
        idx = pd.to_datetime(df.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        df.index = pd.DatetimeIndex(idx, name=DATE)
        df = df[~df.index.duplicated(keep="last")].sort_index()

        keep = [c for c in OHLCV if c in df.columns]
        df = df[keep].apply(pd.to_numeric, errors="coerce").astype("float64")

        # 校验：丢弃坏行（high<low、价格 NaN/≤0）
        n0 = len(df)
        price_cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
        bad = df[price_cols].isna().any(axis=1) | (df[price_cols] <= 0).any(axis=1)
        if HIGH in df.columns and LOW in df.columns:
            bad = bad | (df[HIGH] < df[LOW])
        df = df[~bad]
        if n0 and (n0 - len(df)) / n0 > 0.5:
            raise DataQualityError(f"坏行比例过高：{n0 - len(df)}/{n0}")
        return df
