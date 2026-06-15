"""回测引擎（详细设计 §8.2）—— 次日生效、计成本、出绩效。"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from quantlab.backtest.strategies import Strategy
from quantlab.constants import CLOSE
from quantlab.core import shift_next_day

_ANN = 252  # 年化交易日


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    returns: pd.Series
    buy_hold: pd.Series
    total_return: float
    cagr: float
    vol: float
    sharpe: float
    max_drawdown: float
    n_trades: int

    def tearsheet(self):
        try:
            import quantstats as qs
        except ImportError as e:
            raise ImportError("需要 quantstats：pip install quantstats") from e
        return qs.reports.metrics(self.returns, mode="full")


class Backtester:
    def __init__(self, cost_bps: float = 5.0) -> None:
        self.cost_bps = cost_bps

    def run(self, df: pd.DataFrame, strategy: Strategy) -> BacktestResult:
        pos = strategy.generate_positions(df).clip(0.0, 1.0)
        pos = shift_next_day(pos)                       # ★ 次日生效，防未来函数
        r = df[CLOSE].pct_change().fillna(0.0)
        turnover = pos.diff().abs().fillna(pos.abs())
        cost = turnover * self.cost_bps / 1e4
        ret = pos * r - cost
        eq = (1.0 + ret).cumprod()

        n = len(eq)
        std = ret.std()
        total = float(eq.iloc[-1] - 1.0)
        cagr = float(eq.iloc[-1] ** (_ANN / n) - 1.0) if n > 0 and eq.iloc[-1] > 0 else 0.0
        vol = float(std * math.sqrt(_ANN)) if std > 0 else 0.0
        sharpe = float(ret.mean() / std * math.sqrt(_ANN)) if std > 0 else 0.0
        max_dd = float((eq / eq.cummax() - 1.0).min())
        n_trades = int((pos.diff().fillna(pos) != 0).sum())
        return BacktestResult(
            equity_curve=eq, returns=ret, buy_hold=(1.0 + r).cumprod(),
            total_return=total, cagr=cagr, vol=vol, sharpe=sharpe,
            max_drawdown=max_dd, n_trades=n_trades,
        )
