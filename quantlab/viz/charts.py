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


def style_timeseries(fig):
    """统一的时间序列交互（同花顺/看盘网站手感）：拖拽平移 + 十字光标。

    看板内嵌图与"下载的可交互 HTML"都会带上这套手感。缩放走滚轮/快捷键（在看板里挂）。
    """
    fig.update_layout(
        dragmode="pan",            # 左键拖拽 = 平移时间轴（默认是框选缩放）
        hovermode="x unified",     # 鼠标移动 → 该时刻各线价格汇总到一个浮窗
        xaxis=dict(                # 竖直十字光标线，贯穿整图
            showspikes=True, spikemode="across", spikesnap="cursor",
            spikethickness=1, spikedash="dot", spikecolor="#888",
        ),
        yaxis=dict(showspikes=True, spikethickness=1, spikedash="dot", spikecolor="#888"),
    )
    return fig


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
    fig.update_layout(title=title, xaxis_rangeslider_visible=False)
    return style_timeseries(fig)


def plot_volume(df: pd.DataFrame):
    go = _go()
    colors = [UP_COLOR if c >= o else DOWN_COLOR for c, o in zip(df[CLOSE], df[OPEN])]
    fig = go.Figure(go.Bar(x=df.index, y=df[VOLUME], name="成交量", marker_color=colors))
    fig.update_layout(title="成交量")
    return style_timeseries(fig)


def plot_equity(result):
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result.equity_curve.index, y=result.equity_curve, name="策略净值"))
    fig.add_trace(go.Scatter(x=result.buy_hold.index, y=result.buy_hold, name="买入持有"))
    fig.update_layout(title="净值对照（起点=1）")
    return style_timeseries(fig)


def plot_drawdown(result):
    go = _go()
    eq = result.equity_curve
    dd = eq / eq.cummax() - 1.0
    fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", name="回撤",
                               line_color="#d62728"))
    fig.update_layout(title="回撤", yaxis_tickformat=".0%")
    return style_timeseries(fig)


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


def plot_securitization(cn: pd.Series, us: pd.Series, cn_pct: pd.Series | None = None):
    """证券化率 / 巴菲特指标对比：中国(每日) vs 美国(季度) + 中国自身历史分位。

    Args:
        cn / us: 市值÷GDP 比率(%)，index=日期。
        cn_pct: 中国比率在自身历史中的分位(%)，画在右轴。
    """
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cn.index, y=cn, mode="lines", name="中国 证券化率%",
                             line_color=UP_COLOR))
    fig.add_trace(go.Scatter(x=us.index, y=us, mode="lines", name="美国 证券化率%",
                             line_color="#1f77b4"))
    fig.add_hline(y=100, line_dash="dash", line_color="#888",
                  annotation_text="100%（市值=GDP）", annotation_position="top left")
    if cn_pct is not None and len(cn_pct):
        fig.add_trace(go.Scatter(x=cn_pct.index, y=cn_pct, mode="lines", yaxis="y2",
                                 name="中国 历史分位%", line=dict(color="#ff7f0e", width=1),
                                 opacity=0.45))
        fig.update_layout(yaxis2=dict(title="历史分位 %", overlaying="y", side="right",
                                      range=[0, 100], showgrid=False))
    fig.update_layout(title="证券化率 / 巴菲特指标：中国 vs 美国",
                      yaxis=dict(title="市值 / GDP  (%)"))
    return style_timeseries(fig)


def plot_allocation_backtest(eq: pd.DataFrame):
    """温度计加减仓走查：策略 vs 买入持有净值(对数左轴) + 仓位(右轴填充)。

    Args:
        eq: 列 ``strategy`` / ``buy_hold`` / ``position``，index=日期。
    """
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq.index, y=eq["position"] * 100, yaxis="y2",
                             name="仓位 %", fill="tozeroy", line=dict(width=0),
                             fillcolor="rgba(255,127,14,0.18)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=eq.index, y=eq["strategy"], name="温度择仓",
                             line_color=UP_COLOR))
    fig.add_trace(go.Scatter(x=eq.index, y=eq["buy_hold"], name="买入持有",
                             line=dict(color="#888", dash="dot")))
    fig.update_layout(
        title="温度计加减仓 走查回测（净值起点=1，左轴对数）",
        yaxis=dict(title="净值", type="log"),
        yaxis2=dict(title="仓位 %", overlaying="y", side="right",
                    range=[0, 100], showgrid=False),
    )
    return style_timeseries(fig)


def plot_compare(series_map: dict[str, pd.Series]):
    """多标的归一化净值对比（起点=1）。"""
    go = _go()
    fig = go.Figure()
    for name, s in series_map.items():
        s = s.dropna()
        if len(s):
            fig.add_trace(go.Scatter(x=s.index, y=s / s.iloc[0], mode="lines", name=name))
    fig.update_layout(title="归一化走势对比（起点=1）")
    return style_timeseries(fig)
