"""跨市场领先预警（详细设计 §8.3 / 12.3）—— 美股 → A股。

用 ``calendar.align_series`` 把 lead 市场的条件对齐到 target 市场的交易日（lag 滞后、无前视），
再用 target 的前向收益统计反应概率（复用 base_rate / edge / Wilson 的同一套口径）。
"""

from __future__ import annotations

import pandas as pd

from quantlab.calendar import TradingCalendar
from quantlab.core import forward_return, mae, wilson_interval
from quantlab.errors import InsufficientData
from quantlab.stats.conditions import Condition
from quantlab.stats.probability import ProbabilityResult


def _crossmarket_stats(
    lead_df: pd.DataFrame,
    tgt_df: pd.DataFrame,
    cond: Condition,
    forward: int,
    calendar: TradingCalendar,
    lag: int,
    min_samples: int,
    name: str,
) -> ProbabilityResult:
    lead_mask = cond(lead_df)                                  # bool, 索引为 lead 日期
    amap = calendar.align_series(lead_df.index, tgt_df.index, lag)  # tgt 日 → lead 日
    aligned = amap.map(lambda d: bool(lead_mask.get(d, False)) if pd.notna(d) else False)
    aligned = aligned.reindex(tgt_df.index).fillna(False).astype(bool)

    fwd = forward_return(tgt_df, forward)
    valid = fwd.notna()
    base = float((fwd[valid] > 0).mean())
    mask = aligned & valid
    f = fwd[mask]
    n = int(mask.sum())
    if n == 0:
        raise InsufficientData(f"跨市场条件 {name} 无样本")

    p_up = float((f > 0).mean())
    win, loss = f[f > 0].mean(), f[f < 0].mean()
    if pd.isna(loss) or loss == 0:
        payoff = float("inf") if not pd.isna(win) else 0.0
    else:
        payoff = float(abs(win / loss)) if not pd.isna(win) else 0.0
    lo, hi = wilson_interval(int((f > 0).sum()), n)
    return ProbabilityResult(
        condition=name, symbol="", forward=forward, n=n, p_up=p_up, base_rate=base,
        edge=p_up - base, ci_low=lo, ci_high=hi, mean_ret=float(f.mean()),
        median_ret=float(f.median()), payoff=payoff,
        mae=float(mae(tgt_df, forward)[mask].mean()), reliable=n >= min_samples,
    )


def crossmarket(
    dm,
    lead: str,
    target: str,
    cond: Condition,
    forward: int = 1,
    lag: int = 1,
    min_samples: int = 30,
) -> ProbabilityResult:
    """如 crossmarket(dm, "US:^IXIC", "CN:000300", drop_gt(0.015))。"""
    lead_df = dm.history(lead)
    tgt_df = dm.history(target)
    name = f"{lead}:{cond.name} → {target}"
    return _crossmarket_stats(lead_df, tgt_df, cond, forward, dm.calendar, lag, min_samples, name)
