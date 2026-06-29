"""A股全市场宽度（market breadth）——供兴登堡凶兆 / McClellan 等内部结构指标。

直接从本地个股日线 ``data/bars/CN/*_1d.parquet`` 聚合（**离线，不联网**），缓存到
``data/macro/cn_breadth.parquet``，``refresh=True`` 才重算。每日输出：

- ``qualified``：拥有满 252 日（≈52 周）窗口且当日有成交的个股数（新高/新低的分母）。
- ``new_high`` / ``new_low``：当日创 252 日新高 / 新低的个股数（基于回调后收盘价）。
- ``adv`` / ``dec``：当日上涨 / 下跌家数（供 McClellan 振荡器）。
- ``traded``：当日有成交的个股数（含次新股，仅作参考分母）。

两个必须知道的口径限制（详见 research/兴登堡凶兆_A股适配与验证.md）：

1. **不复权 → 送转伪新低**：A股本地 bar 取不复权价（见 akshare_source）。10 送 10 之类
   除权会让价格瞬间腰斩、伪造一根「新低」。这里对**单日跌幅超过 ±20% 涨跌停板**
   （收盘比 < ``SPLIT_RATIO``=0.72）的个股做后向复权折算，剔除除权跳空；现金分红
   （<3% 小跳空）影响可忽略，不处理。
2. **生存者偏差**：本地个股集合只含**当前仍上市**的股票，已退市/暂停（多半是暴跌股）
   不在内 → 历史**新低被系统性低估**。故本数据对「底部/新低」偏保守，结论需据此打折。

只纳入主板/创业板/科创板正股（剔除 ETF/基金 5xx·159·588，以及 2021 后才有的北交所 920，
保持全历史口径一致）。
"""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

from quantlab.datasources.valuation_source import _macro_dir

WIN = 252  # 52 周交易日
SPLIT_RATIO = 0.72  # 单日收盘比 < 此值视为除权（送转），做后向复权
# 主板(000/001/002/003·600/601/603/605) + 创业板(300/301/302) + 科创板(688/689) 正股
STOCK_PREFIXES = ("000", "001", "002", "003", "300", "301", "302",
                  "600", "601", "603", "605", "688", "689")
_MASTER_INDEX = "cn_index_000001.parquet"  # 上证综指日历做主交易日轴


def _back_adjust(close: pd.Series) -> pd.Series:
    """后向复权：把除权跳空（单日跌幅 > 涨跌停板）折进历史价，使 52 周高低不被送转污染。

    从最近往最早走，遇到 ``ratio<SPLIT_RATIO`` 的除权日，就把**该日之前**的所有价格
    乘以跳空比例（锚定近端原始价）。现金分红等小跳空不触发，保持原值。
    """
    ratios = (close / close.shift(1)).to_numpy()
    factor = np.ones(len(close))
    cum = 1.0
    for i in range(len(close) - 1, 0, -1):
        factor[i] = cum
        if ratios[i] < SPLIT_RATIO:
            cum *= ratios[i]
    factor[0] = cum
    return close * factor


def _build(data_root: str) -> pd.DataFrame:
    bars_dir = os.path.join(data_root, "bars", "CN")
    files = sorted(glob.glob(os.path.join(bars_dir, "*_1d.parquet")))
    files = [f for f in files if os.path.basename(f).startswith(STOCK_PREFIXES)]
    if not files:
        raise RuntimeError(f"无个股日线可聚合：{bars_dir}")

    master = pd.read_parquet(os.path.join(_macro_dir(data_root), _MASTER_INDEX))
    master_idx = master.index
    n = len(master_idx)
    acc = {k: np.zeros(n, dtype=np.int32)
           for k in ("qualified", "new_high", "new_low", "adv", "dec", "traded")}

    for f in files:
        try:
            s = pd.read_parquet(f, columns=["close"])["close"].dropna()
        except Exception:  # noqa: BLE001 —— 单只坏文件不阻断全市场聚合
            continue
        if len(s) < 2:
            continue
        adj = _back_adjust(s)
        roll_max = adj.rolling(WIN, min_periods=WIN).max()
        roll_min = adj.rolling(WIN, min_periods=WIN).min()
        qualified = roll_max.notna()
        chg = adj.diff()
        # 只把落在主日历内的交易日入桶；-1=日历外(如 2005 前)直接丢弃，
        # 避免被 clip 堆到首/末桶（rolling 仍在整段历史上算，窗口口径不受影响）。
        pos = master_idx.get_indexer(s.index)
        m = pos >= 0
        pos = pos[m]
        np.add.at(acc["traded"], pos, 1)
        np.add.at(acc["qualified"], pos, qualified.to_numpy().astype(np.int32)[m])
        np.add.at(acc["new_high"], pos, (qualified & (adj >= roll_max)).to_numpy().astype(np.int32)[m])
        np.add.at(acc["new_low"], pos, (qualified & (adj <= roll_min)).to_numpy().astype(np.int32)[m])
        np.add.at(acc["adv"], pos, (chg > 0).to_numpy().astype(np.int32)[m])
        np.add.at(acc["dec"], pos, (chg < 0).to_numpy().astype(np.int32)[m])

    out = pd.DataFrame(acc, index=master_idx)
    out.index.name = "date"
    return out[out["traded"] > 0]


def cn_breadth(data_root: str = "data/", refresh: bool = False) -> pd.DataFrame:
    """A股全市场宽度（日度）。缓存 ``data/macro/cn_breadth.parquet``。

    列：qualified / new_high / new_low / adv / dec / traded（见模块 docstring）。
    """
    cache = _macro_dir(data_root) / "cn_breadth.parquet"
    if cache.exists() and not refresh:
        return pd.read_parquet(cache)
    df = _build(data_root)
    df.to_parquet(cache)
    return df
