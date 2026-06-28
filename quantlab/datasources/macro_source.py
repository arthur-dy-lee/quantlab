"""宏观指标数据源：证券化率 / 巴菲特指标（股市总市值 ÷ GDP）。

- 中国：akshare ``stock_buffett_index_lg`` —— 每日「全市场总市值 / GDP」（单位：亿元），
  含历史可算分位。
- 美国：FRED 公共 CSV —— 企业股权市值 ``NCBEILQ027S``(百万美元) ÷ 名义 GDP ``GDP``(十亿美元)，
  季度、1945 至今、无需 API key。

两者均落地 parquet 缓存，离线复用；``refresh=True`` 才联网刷新（与看板里的 dm 自动下载同理）。
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import pandas as pd

_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def _macro_dir(data_root: str) -> Path:
    d = Path(data_root) / "macro"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fred_csv(sid: str) -> pd.DataFrame:
    """拉取单条 FRED 序列（带 UA，否则 403/404）。返回 date + 数值两列。"""
    req = urllib.request.Request(_FRED.format(sid=sid), headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read()  # noqa: S310 —— 固定 FRED 域名
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = ["date", sid]
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna()


def china_securitization(data_root: str = "data/", refresh: bool = False) -> pd.DataFrame:
    """中国证券化率（每日）。index=日期；列：mktcap_yi, gdp_yi（亿元）, ratio(%)。"""
    cache = _macro_dir(data_root) / "cn_buffett.parquet"
    if cache.exists() and not refresh:
        return pd.read_parquet(cache)

    import akshare as ak

    raw = ak.stock_buffett_index_lg()  # 列：日期 收盘价 总市值 GDP（单位：亿元）
    df = pd.DataFrame(
        {"mktcap_yi": raw["总市值"].to_numpy(float), "gdp_yi": raw["GDP"].to_numpy(float)},
        index=pd.DatetimeIndex(pd.to_datetime(raw["日期"])),
    )
    df.index.name = "date"
    df = df[df["gdp_yi"] > 0].sort_index()
    df["ratio"] = df["mktcap_yi"] / df["gdp_yi"] * 100.0
    df.to_parquet(cache)
    return df


def us_securitization(data_root: str = "data/", refresh: bool = False) -> pd.DataFrame:
    """美国证券化率（季度，FRED）。index=日期；列：equities_b, gdp_b（十亿美元）, ratio(%)。"""
    cache = _macro_dir(data_root) / "us_buffett.parquet"
    if cache.exists() and not refresh:
        return pd.read_parquet(cache)

    eq = _fred_csv("NCBEILQ027S")  # 企业股权市值，百万美元
    gd = _fred_csv("GDP")          # 名义 GDP，十亿美元
    m = pd.merge_asof(eq.sort_values("date"), gd.sort_values("date"), on="date")
    out = pd.DataFrame(
        {"equities_b": m["NCBEILQ027S"].to_numpy(float) / 1000.0,  # 百万→十亿
         "gdp_b": m["GDP"].to_numpy(float)},
        index=pd.DatetimeIndex(m["date"]),
    )
    out.index.name = "date"
    out = out.dropna().sort_index()
    out["ratio"] = out["equities_b"] / out["gdp_b"] * 100.0
    out.to_parquet(cache)
    return out


def historical_percentile(ratio: pd.Series) -> pd.Series:
    """每个时点的取值，在「截至当时的全部历史」中的分位（%）。

    扩张窗口、只用过去数据，避免未来函数；100 ≈ 历史最高，0 ≈ 历史最低。
    """
    return ratio.expanding(min_periods=1).apply(
        lambda w: float((w <= w.iloc[-1]).mean() * 100.0), raw=False
    )
