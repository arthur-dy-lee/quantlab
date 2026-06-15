"""组合回测 + 资金管理（详细设计 §17 / OPT-9）。

多标的、按目标权重每日再平衡、计再平衡成本。等权或自定义权重。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from quantlab.constants import CLOSE

_ANN = 252


@dataclass
class PortfolioResult:
    equity_curve: pd.Series
    returns: pd.Series
    weights: dict[str, float]
    total_return: float
    cagr: float
    vol: float
    sharpe: float
    max_drawdown: float


class PortfolioBacktester:
    def __init__(self, cost_bps: float = 5.0) -> None:
        self.cost_bps = cost_bps

    def run(self, dfs: dict[str, pd.DataFrame], weights: dict[str, float] | None = None) -> PortfolioResult:
        closes = pd.DataFrame({s: df[CLOSE] for s, df in dfs.items()}).dropna()
        if closes.empty or closes.shape[1] == 0:
            raise ValueError("组合无共同交易日数据")
        syms = list(closes.columns)
        if weights is None:
            w = pd.Series(1.0 / len(syms), index=syms)
        else:
            w = pd.Series(weights).reindex(syms).fillna(0.0)
            w = w / w.sum()

        R = closes.pct_change().fillna(0.0)
        rets = []
        prev_w = w.copy()
        for t in range(len(R)):
            r_t = R.iloc[t]
            drifted = prev_w * (1.0 + r_t)
            total = drifted.sum()
            drifted = drifted / total if total else prev_w
            turnover = float((w - drifted).abs().sum()) if t > 0 else 0.0
            gross = float((w * r_t).sum())
            rets.append(gross - turnover * self.cost_bps / 1e4)
            prev_w = w  # 再平衡回目标
        ret = pd.Series(rets, index=R.index)
        eq = (1.0 + ret).cumprod()

        n = len(eq)
        std = ret.std()
        return PortfolioResult(
            equity_curve=eq, returns=ret, weights=w.to_dict(),
            total_return=float(eq.iloc[-1] - 1.0),
            cagr=float(eq.iloc[-1] ** (_ANN / n) - 1.0) if n and eq.iloc[-1] > 0 else 0.0,
            vol=float(std * math.sqrt(_ANN)) if std > 0 else 0.0,
            sharpe=float(ret.mean() / std * math.sqrt(_ANN)) if std > 0 else 0.0,
            max_drawdown=float((eq / eq.cummax() - 1.0).min()),
        )
