"""Streamlit 本地仪表盘（详细设计 §10.3）。

运行：``streamlit run quantlab/dashboard/app.py``（需 ``pip install -e '.[dashboard]'``）。
调用同一功能层 + viz。普通 import 不触发 streamlit（仅 streamlit run 时执行 main）。
"""

from __future__ import annotations


def main() -> None:
    import streamlit as st

    from quantlab.backtest.engine import Backtester
    from quantlab.backtest.strategies import DualMAStrategy, RsiReversionStrategy
    from quantlab.bootstrap import build_app
    from quantlab.constants import DEFAULT_INDICATORS
    from quantlab.indicators.technical import add_indicators
    from quantlab.stats.conditions import drop_gt, n_down_days
    from quantlab.stats.probability import probability
    from quantlab.viz.charts import plot_candles, plot_equity, plot_probability

    st.set_page_config(page_title="QuantLab", layout="wide")
    st.title("QuantLab 仪表盘")

    dm = build_app()
    symbol = st.sidebar.text_input("标的", "US:AAPL")
    overlays = st.sidebar.multiselect("指标叠加", DEFAULT_INDICATORS, default=["ma5", "ma20"])

    if not symbol:
        st.stop()
    df = add_indicators(dm.history(symbol))

    st.subheader("K线 + 指标")
    st.plotly_chart(plot_candles(df, overlays), use_container_width=True)

    tab_bt, tab_stat = st.tabs(["回测", "条件概率"])
    with tab_bt:
        which = st.selectbox("策略", ["dualma", "rsi"])
        strat = RsiReversionStrategy() if which == "rsi" else DualMAStrategy()
        res = Backtester().run(df, strat)
        c1, c2, c3 = st.columns(3)
        c1.metric("总收益", f"{res.total_return:.1%}")
        c2.metric("夏普", f"{res.sharpe:.2f}")
        c3.metric("最大回撤", f"{res.max_drawdown:.1%}")
        st.plotly_chart(plot_equity(res), use_container_width=True)
    with tab_stat:
        pct = st.slider("单日跌幅阈值", 0.005, 0.05, 0.015, 0.005)
        n = st.slider("连跌天数", 1, 5, 1)
        cond = drop_gt(pct) & n_down_days(n) if n > 1 else drop_gt(pct)
        r = probability(df, cond, 1, dm.cfg.stats_min_samples, symbol)
        st.write(f"上涨概率 **{r.p_up:.1%}**，基准 {r.base_rate:.1%}，edge **{r.edge:+.1%}**，"
                 f"N={r.n}，95%CI {r.ci_low:.1%}~{r.ci_high:.1%}")
        st.plotly_chart(plot_probability(r), use_container_width=True)


if __name__ == "__main__":
    main()
