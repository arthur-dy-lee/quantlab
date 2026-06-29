"""兴登堡凶兆（Hindenburg Omen）A股适配。详见 research/兴登堡凶兆_A股适配与验证.md。

原始信号（NYSE）的核心直觉：市场仍在上升趋势中，却同时出现**异常多的 52 周新高
与新低**——内部「分裂」，多空两极分化、宽度在表面之下恶化，是顶部不稳的前兆。

每个交易日四个条件（A股口径，分母用「满 252 日窗口的正股数」``qualified``）：

1. 新高占比 ≥ ``threshold`` **且** 新低占比 ≥ ``threshold``（经典 2.2%；二者取小者达标）。
2. 新高家数 ≤ 2 × 新低家数（确保新低不是零头，是真分裂而非普涨）。
3. 指数处于上升趋势：``close[t] > close[t-roc_win]``（经典 10 周≈50 日动量为正）。
4. McClellan 振荡器 < 0（宽度动能转负）。

四条全满足 = 一个「凶兆日」。**确认**：36 个交易日窗口内出现 ≥2 个凶兆日（聚类）。
信号自确认日起「活跃」``active_days``（经典 30 交易日）。

McClellan 用**比例调整版**（ratio-adjusted，适配 A股上市数从 ~1500 涨到 ~5000）：
``RANA = (adv−dec)/(adv+dec)·1000``，振荡器 = ``EMA19(RANA) − EMA39(RANA)``。

**无未来函数**：所有列只用截至 t 的数据；信号用于交易须次日生效（见 core.shift_next_day）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.datasources.breadth_source import cn_breadth

THRESHOLD = 0.022     # 新高/新低占比阈值（经典 2.2%）
ROC_WIN = 50          # 上升趋势判定窗口（≈10 周）
CONFIRM_WIN = 36      # 确认聚类窗口（交易日）
CONFIRM_MIN = 2       # 窗口内 ≥2 个凶兆日才确认
ACTIVE_DAYS = 30      # 确认后信号活跃期（交易日）
MIN_QUALIFIED = 200   # 分母太小（早年）不计信号，避免占比噪声


def mcclellan(breadth: pd.DataFrame, fast: int = 19, slow: int = 39) -> pd.Series:
    """比例调整 McClellan 振荡器。adv+dec=0 的停牌极端日按 0 净宽度处理。"""
    net = breadth["adv"] - breadth["dec"]
    denom = (breadth["adv"] + breadth["dec"]).replace(0, np.nan)
    rana = (net / denom * 1000.0).fillna(0.0)
    return (rana.ewm(span=fast, adjust=False).mean()
            - rana.ewm(span=slow, adjust=False).mean()).rename("mcclellan")


def omen_table(
    index_px: pd.DataFrame,
    breadth: pd.DataFrame | None = None,
    threshold: float = THRESHOLD,
    roc_win: int = ROC_WIN,
    confirm_win: int = CONFIRM_WIN,
    active_days: int = ACTIVE_DAYS,
    data_root: str = "data/",
    refresh: bool = False,
) -> pd.DataFrame:
    """逐日兴登堡凶兆诊断表。

    参数 ``index_px``：上升趋势判定所用指数 OHLC（需含 close，建议上证综指/中证全指）。
    返回 DataFrame（index=date），列：
    nh_pct/nl_pct/mcclellan/uptrend、cond1..cond4、``omen``（凶兆日）、
    ``confirmed``（确认日：36 日窗口内 ≥2 凶兆且当日为凶兆）、``active``（活跃期内）。
    """
    if breadth is None:
        breadth = cn_breadth(data_root, refresh)
    b = breadth[breadth["qualified"] >= MIN_QUALIFIED].copy()
    nh = b["new_high"] / b["qualified"]
    nl = b["new_low"] / b["qualified"]
    mc = mcclellan(breadth).reindex(b.index)

    close = index_px["close"].reindex(b.index).ffill()
    uptrend = close > close.shift(roc_win)

    cond1 = (nh >= threshold) & (nl >= threshold)
    cond2 = b["new_high"] <= 2 * b["new_low"]
    cond3 = uptrend
    cond4 = mc < 0
    omen = (cond1 & cond2 & cond3 & cond4).fillna(False)

    cluster = omen.rolling(confirm_win, min_periods=1).sum()
    confirmed = omen & (cluster >= CONFIRM_MIN)
    # 活跃期：确认日起 active_days 个交易日内为 True
    active = confirmed.rolling(active_days, min_periods=1).max().astype(bool)

    out = pd.DataFrame({
        "nh_pct": nh, "nl_pct": nl, "mcclellan": mc, "uptrend": uptrend,
        "cond1_split": cond1, "cond2_lows": cond2, "cond3_uptrend": cond3,
        "cond4_mcclellan": cond4, "omen": omen, "confirmed": confirmed, "active": active,
    })
    return out


def episodes(omen: pd.DataFrame, gap: int = ACTIVE_DAYS) -> pd.DatetimeIndex:
    """把相邻确认日并成「事件」：去掉 ``gap`` 交易日内的重复确认，返回每个事件的首确认日。"""
    conf = omen.index[omen["confirmed"].to_numpy()]
    if len(conf) == 0:
        return pd.DatetimeIndex([])
    keep = [conf[0]]
    last = omen.index.get_loc(conf[0])
    for d in conf[1:]:
        i = omen.index.get_loc(d)
        if i - last > gap:
            keep.append(d)
        last = i
    return pd.DatetimeIndex(keep)
