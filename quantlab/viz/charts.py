"""图表（详细设计 §10.1）—— plotly 交互图，懒加载。"""

from __future__ import annotations

import pandas as pd

from quantlab.constants import CLOSE, HIGH, LOW, OPEN, VOLUME
from quantlab.core import forward_return
from quantlab.errors import SourceUnavailable

# A 股习惯：涨红、跌绿
UP_COLOR = "#d62728"    # 涨 = 红
DOWN_COLOR = "#2ca02c"  # 跌 = 绿


def _go():
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise SourceUnavailable("plotly 未安装：pip install -e '.[dashboard]'") from e
    return go


def plot_candles(df: pd.DataFrame, indicators: list[str] | None = None, title: str = "K线 + 指标"):
    go = _go()
    fig = go.Figure(
        data=[go.Candlestick(x=df.index, open=df[OPEN], high=df[HIGH],
                             low=df[LOW], close=df[CLOSE], name="K线",
                             increasing_line_color=UP_COLOR, increasing_fillcolor=UP_COLOR,
                             decreasing_line_color=DOWN_COLOR, decreasing_fillcolor=DOWN_COLOR)]
    )
    for col in indicators or []:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=col))
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, hovermode="x unified")
    return fig


def plot_volume(df: pd.DataFrame):
    go = _go()
    colors = [UP_COLOR if c >= o else DOWN_COLOR for c, o in zip(df[CLOSE], df[OPEN])]
    fig = go.Figure(go.Bar(x=df.index, y=df[VOLUME], name="成交量", marker_color=colors))
    fig.update_layout(title="成交量")
    return fig


def plot_equity(result):
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result.equity_curve.index, y=result.equity_curve, name="策略净值"))
    fig.add_trace(go.Scatter(x=result.buy_hold.index, y=result.buy_hold, name="买入持有"))
    fig.update_layout(title="净值对照（起点=1）", hovermode="x unified")
    return fig


def plot_drawdown(result):
    go = _go()
    eq = result.equity_curve
    dd = eq / eq.cummax() - 1.0
    fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", name="回撤",
                               line_color="#d62728"))
    fig.update_layout(title="回撤", yaxis_tickformat=".0%")
    return fig


def plot_probability(result):
    go = _go()
    fig = go.Figure(data=[go.Bar(x=["条件概率", "无条件基准率"],
                                 y=[result.p_up, result.base_rate],
                                 marker_color=["#d62728", "#7f7f7f"],
                                 text=[f"{result.p_up:.1%}", f"{result.base_rate:.1%}"])])
    fig.update_layout(title=f"{result.condition}  edge {result.edge:+.1%}  (N={result.n})",
                      yaxis_tickformat=".0%")
    return fig


def plot_return_hist(df: pd.DataFrame, cond, forward: int = 1):
    """条件命中 vs 全样本的"未来 N 日收益"分布直方图。"""
    go = _go()
    fwd = forward_return(df, forward).dropna() * 100.0
    mask = cond(df).reindex(fwd.index).fillna(False)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=fwd, name="全样本", opacity=0.45, nbinsx=60))
    fig.add_trace(go.Histogram(x=fwd[mask], name="条件命中", opacity=0.7, nbinsx=60,
                               marker_color="#d62728"))
    fig.update_layout(barmode="overlay", title=f"未来{forward}日收益分布(%)",
                      xaxis_title="收益 %", yaxis_title="频数")
    return fig


def plot_compare(series_map: dict[str, pd.Series]):
    """多标的归一化净值对比（起点=1）。"""
    go = _go()
    fig = go.Figure()
    for name, s in series_map.items():
        s = s.dropna()
        if len(s):
            fig.add_trace(go.Scatter(x=s.index, y=s / s.iloc[0], mode="lines", name=name))
    fig.update_layout(title="归一化走势对比（起点=1）", hovermode="x unified")
    return fig
