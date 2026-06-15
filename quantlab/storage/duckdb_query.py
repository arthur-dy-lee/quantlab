"""DuckDB 横截面查询层（详细设计 §7.3 / OPT-10）。

叠加在 Parquet 之上：直接 SQL 查所有标的的 Parquet，做"某天全市场筛选"等横截面查询。
不替换 Parquet，按需启用（``pip install -e '.[query]'``）。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from quantlab.enums import Freq
from quantlab.errors import SourceUnavailable


def _duckdb():
    try:
        import duckdb
    except ImportError as e:
        raise SourceUnavailable("duckdb 未安装：pip install -e '.[query]'") from e
    return duckdb


def cross_section(root: str = "data/", freq: Freq = Freq.DAY, where: str = "TRUE") -> pd.DataFrame:
    """所有标的的**最新一根** bar 组成横截面，按 ``where`` 过滤（DuckDB 原地查 Parquet）。

    返回列：market, code, date, open, high, low, close, volume。
    ``where`` 为作用在这些列上的 SQL（如 ``"close > open"``）。
    """
    duckdb = _duckdb()
    glob = str(Path(root) / "bars" / "*" / f"*_{freq.value}.parquet")
    q = f"""
      WITH b AS (
        SELECT *, filename FROM read_parquet('{glob}', filename=true, union_by_name=true)
      ),
      r AS (
        SELECT *, row_number() OVER (PARTITION BY filename ORDER BY "date" DESC) AS rn FROM b
      )
      SELECT
        regexp_extract(filename, 'bars/([^/]+)/', 1) AS market,
        regexp_extract(filename, '/([^/]+)_{freq.value}\\.parquet$', 1) AS code,
        "date", open, high, low, close, volume
      FROM r
      WHERE rn = 1 AND ({where})
      ORDER BY market, code
    """
    con = duckdb.connect()
    try:
        return con.execute(q).df()
    finally:
        con.close()
