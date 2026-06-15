"""存储层（详细设计 §6）—— Parquet(原始价) + SQLite(元数据) + 复权事件。

``load_factors`` 返回存储的复权**事件**(actions)，由 ``adjust.compute_factors`` 现算因子。
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from quantlab.constants import DATE, OHLCV
from quantlab.enums import Freq
from quantlab.symbols import Symbol

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bars_meta (
  symbol TEXT, freq TEXT, start TEXT, "end" TEXT, rows INTEGER,
  source TEXT, instrument_type TEXT, updated_at TEXT,
  PRIMARY KEY(symbol, freq));
CREATE TABLE IF NOT EXISTS etf_meta (
  symbol TEXT PRIMARY KEY, nav REAL, premium_discount REAL,
  tracking_index TEXT, theme TEXT, constituents TEXT);
CREATE TABLE IF NOT EXISTS notify_log (
  symbol TEXT, signal TEXT, sent_at TEXT,
  PRIMARY KEY(symbol, signal, sent_at));
"""


@dataclass
class BarMeta:
    symbol: str
    freq: str
    start: date
    end: date
    rows: int
    source: str
    instrument_type: str
    updated_at: datetime


def _safe(code: str) -> str:
    return code.replace("/", "_").replace(":", "_")


def _empty_ohlcv() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], name=DATE)
    return pd.DataFrame({c: pd.Series(dtype="float64") for c in OHLCV}, index=idx)


class BarRepository:
    def __init__(self, root: str = "data/") -> None:
        self.root = Path(root)
        (self.root / "bars").mkdir(parents=True, exist_ok=True)
        (self.root / "adjust").mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "quantlab.db"
        self._ensure_schema()

    # ---- paths ----
    def _bars_path(self, sym: Symbol, freq: Freq) -> Path:
        return self.root / "bars" / sym.market.value / f"{_safe(sym.code)}_{freq.value}.parquet"

    def _adjust_path(self, sym: Symbol) -> Path:
        return self.root / "adjust" / sym.market.value / f"{_safe(sym.code)}.parquet"

    # ---- schema ----
    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.executescript(_SCHEMA)

    # ---- read ----
    def load(self, sym: Symbol, freq: Freq) -> pd.DataFrame:
        p = self._bars_path(sym, freq)
        if not p.exists():
            return _empty_ohlcv()
        df = pd.read_parquet(p)
        df.index = pd.DatetimeIndex(df.index, name=DATE)
        return df.sort_index()

    def load_factors(self, sym: Symbol) -> pd.DataFrame | None:
        p = self._adjust_path(sym)
        if not p.exists():
            return None
        df = pd.read_parquet(p)
        df.index = pd.DatetimeIndex(df.index, name=DATE)
        return df.sort_index()

    def meta(self, sym: Symbol, freq: Freq) -> BarMeta | None:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                'SELECT symbol,freq,start,"end",rows,source,instrument_type,updated_at '
                "FROM bars_meta WHERE symbol=? AND freq=?",
                (sym.key, freq.value),
            ).fetchone()
        return self._row_to_meta(row) if row else None

    def catalog(self) -> list[BarMeta]:
        with sqlite3.connect(self.db_path) as con:
            rows = con.execute(
                'SELECT symbol,freq,start,"end",rows,source,instrument_type,updated_at '
                "FROM bars_meta ORDER BY symbol,freq"
            ).fetchall()
        return [self._row_to_meta(r) for r in rows]

    @staticmethod
    def _row_to_meta(r) -> BarMeta:
        return BarMeta(
            symbol=r[0], freq=r[1],
            start=date.fromisoformat(r[2]), end=date.fromisoformat(r[3]),
            rows=r[4], source=r[5], instrument_type=r[6],
            updated_at=datetime.fromisoformat(r[7]),
        )

    # ---- write ----
    def save(
        self,
        sym: Symbol,
        freq: Freq,
        bars: pd.DataFrame,
        actions: pd.DataFrame | None = None,
        source: str = "",
    ) -> BarMeta:
        merged = self._merge(self.load(sym, freq), bars)
        self._atomic_write(self._bars_path(sym, freq), merged)
        if actions is not None and not actions.empty:
            self._atomic_write(self._adjust_path(sym), self._merge(self.load_factors(sym), actions))
        return self._upsert_meta(sym, freq, merged, source)

    @staticmethod
    def _merge(existing: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
        if existing is None or existing.empty:
            out = new
        else:
            out = pd.concat([existing, new])
        out = out[~out.index.duplicated(keep="last")].sort_index()
        return out

    def _atomic_write(self, path: Path, df: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        df.to_parquet(tmp)
        os.replace(tmp, path)

    def _upsert_meta(self, sym: Symbol, freq: Freq, merged: pd.DataFrame, source: str) -> BarMeta:
        m = BarMeta(
            symbol=sym.key, freq=freq.value,
            start=merged.index[0].date(), end=merged.index[-1].date(),
            rows=len(merged), source=source,
            instrument_type=sym.instrument_type.value, updated_at=datetime.now(),
        )
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                'INSERT OR REPLACE INTO bars_meta '
                '(symbol,freq,start,"end",rows,source,instrument_type,updated_at) '
                "VALUES (?,?,?,?,?,?,?,?)",
                (m.symbol, m.freq, m.start.isoformat(), m.end.isoformat(), m.rows,
                 m.source, m.instrument_type, m.updated_at.isoformat()),
            )
        return m
