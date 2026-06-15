"""条件概率统计（详细设计 §8.3）★ —— base_rate / edge / Wilson CI / payoff / MAE。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quantlab.core import forward_return, mae, wilson_interval
from quantlab.errors import InsufficientData
from quantlab.stats.conditions import Condition


@dataclass
class ProbabilityResult:
    condition: str
    symbol: str
    forward: int
    n: int
    p_up: float
    base_rate: float
    edge: float            # p_up - base_rate
    ci_low: float
    ci_high: float         # Wilson(p_up)
    mean_ret: float
    median_ret: float
    payoff: float          # 平均盈 / 平均亏
    mae: float             # 平均最大不利波动（下行风险）
    reliable: bool         # n >= min_samples


def probability(
    df: pd.DataFrame,
    cond: Condition,
    forward: int = 1,
    min_samples: int = 30,
    symbol: str = "",
) -> ProbabilityResult:
    fwd = forward_return(df, forward)
    valid = fwd.notna()
    base = float((fwd[valid] > 0).mean())

    mask = cond(df) & valid
    f = fwd[mask]
    n = int(mask.sum())
    if n == 0:
        raise InsufficientData(f"条件 {cond.name} 无样本")

    p_up = float((f > 0).mean())
    win = f[f > 0].mean()
    loss = f[f < 0].mean()
    if pd.isna(loss) or loss == 0:
        payoff = float("inf") if not pd.isna(win) else 0.0
    else:
        payoff = float(abs(win / loss)) if not pd.isna(win) else 0.0

    mae_val = float(mae(df, forward)[mask].mean())
    lo, hi = wilson_interval(int((f > 0).sum()), n)
    return ProbabilityResult(
        condition=cond.name, symbol=symbol, forward=forward, n=n,
        p_up=p_up, base_rate=base, edge=p_up - base, ci_low=lo, ci_high=hi,
        mean_ret=float(f.mean()), median_ret=float(f.median()),
        payoff=payoff, mae=mae_val, reliable=n >= min_samples,
    )
