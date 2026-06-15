"""图表（详细设计 §10.1）—— plotly 交互图，懒加载。"""

from __future__ import annotations

import pandas as pd

from quantlab.constants import CLOSE, HIGH, LOW, OPEN
from quantlab.errors import SourceUnavailable


def _go():
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise SourceUnavailable("plotly 未安装：pip install -e '.[dashboard]'") from e
    return go


def plot_candles(df: pd.DataFrame, indicators: list[str] | None = None):
    go = _go()
    fig = go.Figure(
        data=[go.Candlestick(x=df.index, open=df[OPEN], high=df[HIGH],
                             low=df[LOW], close=df[CLOSE], name="K线")]
    )
    for col in indicators or []:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=col))
    fig.update_layout(title="K线 + 指标", xaxis_rangeslider_visible=False)
    return fig


def plot_equity(result):
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result.equity_curve.index, y=result.equity_curve, name="策略净值"))
    fig.add_trace(go.Scatter(x=result.buy_hold.index, y=result.buy_hold, name="买入持有"))
    fig.update_layout(title="净值对照")
    return fig


def plot_probability(result):
    go = _go()
    fig = go.Figure(data=[go.Bar(x=["条件概率", "无条件基准率"],
                                 y=[result.p_up, result.base_rate],
                                 marker_color=["#d62728", "#7f7f7f"])])
    fig.update_layout(title=f"{result.condition}  edge {result.edge:+.1%}  (N={result.n})",
                      yaxis_tickformat=".0%")
    return fig
