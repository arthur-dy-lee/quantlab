"""市场温度计 v1 指标取数（A股）。详见 research/市场温度计_v1详细设计.md。

全部走 akshare，落地 parquet 缓存（data/macro/），``refresh=True`` 才联网刷新
（与 macro_source 同一套约定）。每个取数函数返回 ``pd.Series``（index=日期）。

- 全市场 PE   ``stock_a_ttm_lyr``        → middlePETTM（中位数 TTM）
- 全市场 PB   ``stock_a_all_pb``         → middlePB（中位数；替破净率）
- 沪深300 PE  ``stock_index_pe_lg``      → 滚动市盈率（供 ERP）
- 10年期国债  ``bond_china_yield``       → 中债国债收益率曲线·10年
- 两融余额    ``stock_margin_sse``       → 融资融券余额（SH，2018 起）
- 总市值      ``stock_buffett_index_lg`` → 总市值（亿元，占比分母；复用 macro_source）

> A股源（东财/legulegu/中债）需能联网；受限网络下 akshare 抛异常，由上层处理。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd


def _macro_dir(data_root: str) -> Path:
    d = Path(data_root) / "macro"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cached(cache: Path, refresh: bool, builder: Callable[[], pd.Series]) -> pd.Series:
    """命中 parquet 则离线返回；否则 builder() 取数后落地。"""
    if cache.exists() and not refresh:
        return pd.read_parquet(cache).iloc[:, 0]
    s = builder()
    s.to_frame().to_parquet(cache)
    return s


def _ak():
    try:
        import akshare as ak
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("akshare 未安装：pip install -e '.[cn]'") from e
    return ak


def _series(values, dates, name: str) -> pd.Series:
    # 用 numpy 数组按位置对齐，避免 pd.Series 按原索引对齐导致全 NaN
    vals = pd.to_numeric(pd.Series(values).reset_index(drop=True), errors="coerce").to_numpy(float)
    s = pd.Series(vals, index=pd.DatetimeIndex(pd.to_datetime(list(dates))), name=name)
    s.index.name = "date"
    s = s[s.notna()].sort_index()
    return s[~s.index.duplicated(keep="last")]


# ── 原始指标 ──────────────────────────────────────────────────────────────

def cn_market_pe(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """全市场中位数 TTM 市盈率（日度，2005 至今）。"""
    def build() -> pd.Series:
        raw = _ak().stock_a_ttm_lyr()
        return _series(raw["middlePETTM"], raw["date"], "pe").pipe(lambda s: s[s > 0])
    return _cached(_macro_dir(data_root) / "cn_market_pe.parquet", refresh, build)


def cn_market_pb(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """全市场中位数市净率（日度，2005 至今）；v1 以此替代破净率。"""
    def build() -> pd.Series:
        raw = _ak().stock_a_all_pb()
        return _series(raw["middlePB"], raw["date"], "pb").pipe(lambda s: s[s > 0])
    return _cached(_macro_dir(data_root) / "cn_market_pb.parquet", refresh, build)


def cn_csi300_pe(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """沪深300 滚动市盈率（日度，2005 至今）；供 ERP 计算。"""
    def build() -> pd.Series:
        raw = _ak().stock_index_pe_lg(symbol="沪深300")
        return _series(raw["滚动市盈率"], raw["日期"], "pe300").pipe(lambda s: s[s > 0])
    return _cached(_macro_dir(data_root) / "cn_csi300_pe.parquet", refresh, build)


def cn_bond_10y(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """10年期国债到期收益率（%，日度）。中债国债收益率曲线·10年。

    ``bond_china_yield`` 单次仅接受 ≤1 年窗口，故按年分页（2010 至今）。
    """
    def build() -> pd.Series:
        from datetime import date
        ak = _ak()
        parts = []
        for yr in range(2010, date.today().year + 1):
            raw = ak.bond_china_yield(start_date=f"{yr}0101", end_date=f"{yr}1231")
            gov = raw[raw["曲线名称"] == "中债国债收益率曲线"]
            if len(gov):
                parts.append(_series(gov["10年"], gov["日期"], "y10"))
        return pd.concat(parts).sort_index() if parts else pd.Series(dtype=float, name="y10")
    return _cached(_macro_dir(data_root) / "cn_bond_10y.parquet", refresh, build)


def cn_margin_sh(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """上交所两融余额（融资余额+融券余额，元，日度，2010 至今）。

    用 ``macro_china_market_margin_sh``（2010 起，含 2015 杠杆牛峰值）而非
    ``stock_margin_sse``（仅 2018 起，会让当前两融占比误显示为历史新高）。
    """
    def build() -> pd.Series:
        raw = _ak().macro_china_market_margin_sh()
        total = pd.to_numeric(raw["融资余额"], errors="coerce") + pd.to_numeric(raw["融券余额"], errors="coerce")
        return _series(total, raw["日期"], "margin").pipe(lambda s: s[s > 0])
    return _cached(_macro_dir(data_root) / "cn_margin_sh.parquet", refresh, build)


def cn_total_mktcap(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """全市场总市值（亿元，日度）。复用 macro_source 的巴菲特指标数据。"""
    from quantlab.datasources.macro_source import china_securitization
    s = china_securitization(data_root=data_root, refresh=refresh)["mktcap_yi"].rename("mktcap")
    return s.sort_index()[~s.sort_index().index.duplicated(keep="last")]


def cn_index_ohlc(symbol: str = "000300", data_root: str = "data/",
                  refresh: bool = False) -> pd.DataFrame:
    """A股指数日线 OHLC（东财 ``index_zh_a_hist``，全历史，6 位裸码）。

    默认沪深300(000300)——2005 起全历史、最可交易的大盘，且 ERP 同口径；
    供加减仓决策层算前向收益与 MAE。中证全指(000985)仅 2011 起，备选。
    （新浪 ``stock_zh_index_daily`` 对部分指数会截断尾部，故弃用。）

    返回 DataFrame：index=date(升序去重)，列 open/high/low/close。
    """
    cache = _macro_dir(data_root) / f"cn_index_{symbol}.parquet"
    if cache.exists() and not refresh:
        return pd.read_parquet(cache)
    from datetime import date
    raw = _ak().index_zh_a_hist(symbol=symbol, period="daily",
                                start_date="20041231", end_date=f"{date.today():%Y%m%d}")
    cn = {"开盘": "open", "最高": "high", "最低": "low", "收盘": "close"}
    df = pd.DataFrame({v: pd.to_numeric(raw[k], errors="coerce") for k, v in cn.items()})
    df.index = pd.DatetimeIndex(pd.to_datetime(raw["日期"]))
    df.index.name = "date"
    df = df.dropna().sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.to_parquet(cache)
    return df


# ── 派生指标 ──────────────────────────────────────────────────────────────

def cn_erp(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """股债性价比 ERP（%）= 沪深300盈利收益率(1/PE×100) − 10年期国债。高=股票便宜。"""
    pe = cn_csi300_pe(data_root, refresh)
    y10 = cn_bond_10y(data_root, refresh)
    ey = (100.0 / pe).rename("ey")
    df = pd.concat([ey, y10], axis=1, sort=True)
    df["y10"] = df["y10"].ffill()           # 国债前向填充对齐到交易日
    df = df.dropna()
    return (df["ey"] - df["y10"]).rename("erp")


def cn_margin_ratio(data_root: str = "data/", refresh: bool = False) -> pd.Series:
    """两融占比 = SH两融余额 / 全市场总市值。绝对量级无意义，取其分位。高=杠杆拥挤。"""
    margin = cn_margin_sh(data_root, refresh)                 # 元
    mktcap_yuan = cn_total_mktcap(data_root, refresh) * 1e8   # 亿元 → 元
    df = pd.concat([margin.rename("m"), mktcap_yuan.rename("c")], axis=1, sort=True)
    df["c"] = df["c"].ffill()
    df = df.dropna()
    df = df[df["c"] > 0]
    return (df["m"] / df["c"]).rename("margin_ratio")
