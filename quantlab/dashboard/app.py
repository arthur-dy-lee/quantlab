"""QuantLab 本地中文看板（详细设计 §10.3）。

运行：``streamlit run quantlab/dashboard/app.py``（需 ``pip install -e '.[dashboard]'``）。
功能：按名称/代码搜索、收藏、主题池、K线/成交量/回测/条件概率/多标的对比、图表下载。
普通 import 不触发 streamlit（仅 streamlit run 时执行 main）。
"""

from __future__ import annotations


def main() -> None:  # noqa: C901 —— 看板线性脚本
    import streamlit as st

    from quantlab.backtest.engine import Backtester
    from quantlab.backtest.strategies import DualMAStrategy, RsiReversionStrategy
    from quantlab.bootstrap import build_app
    from quantlab.catalog import build_names, load_favorites, load_names, toggle_favorite
    from quantlab.constants import CLOSE, DEFAULT_INDICATORS
    from quantlab.enums import Adjust, Freq
    from quantlab.errors import InsufficientData
    from quantlab.indicators.technical import add_indicators
    from quantlab.stats.conditions import drop_gt, n_down_days, rsi_lt
    from quantlab.stats.probability import probability
    from quantlab.stats.sizing import build_sizer
    from quantlab.viz.charts import (
        plot_candles, plot_compare, plot_drawdown, plot_equity,
        plot_probability, plot_return_hist, plot_volume,
    )

    st.set_page_config(page_title="QuantLab 量化看板", page_icon="📊", layout="wide")
    st.markdown("<style>#MainMenu{visibility:hidden}footer{visibility:hidden}</style>",
                unsafe_allow_html=True)
    st.title("📊 QuantLab 量化看板")

    import streamlit.components.v1 as components

    _CFG = {"scrollZoom": True, "displaylogo": False}  # 滚轮缩放 + 去 logo

    def _chart(fig):
        st.plotly_chart(fig, use_container_width=True, config=_CFG)

    # 时间序列图：滚轮只缩 X 轴，Y 随可见区间自适应（plotly relayout JS 回调）
    _YJS = """
    var gd=document.getElementById('{plot_id}');
    function _ry(){
      var xa=gd._fullLayout&&gd._fullLayout.xaxis; if(!xa||!xa.range) return;
      var x0=new Date(xa.range[0]).getTime(), x1=new Date(xa.range[1]).getTime();
      var lo=Infinity, hi=-Infinity;
      (gd.data||[]).forEach(function(t){
        var xs=t.x; if(!xs) return;
        for(var i=0;i<xs.length;i++){
          var v=new Date(xs[i]).getTime(); if(v<x0||v>x1) continue;
          if(t.type==='candlestick'){ if(t.low[i]<lo)lo=t.low[i]; if(t.high[i]>hi)hi=t.high[i]; }
          else if(t.y){ var y=t.y[i]; if(y<lo)lo=y; if(y>hi)hi=y; }
        }
      });
      if(lo<hi){ var p=(hi-lo)*0.06; Plotly.relayout(gd,{'yaxis.range':[lo-p,hi+p]}); }
    }
    gd.on('plotly_relayout', function(e){ if(('xaxis.range[0]' in e)||e['xaxis.autorange']) setTimeout(_ry,30); });
    """

    def render_xzoom(fig, height=520):
        # 图自身高度跟 iframe 一致，否则默认 450px 会被矮 iframe 截掉底部 X 轴
        fig.update_layout(height=height, margin=dict(l=40, r=20, t=40, b=44))
        html = fig.to_html(include_plotlyjs="cdn", full_html=True, config=_CFG, post_script=_YJS)
        components.html(html, height=height, scrolling=False)

    dm = build_app()
    root = dm.cfg.data_root
    cached = [m.symbol for m in dm.catalog()]
    if not cached:
        st.warning("本地暂无数据。请先在终端运行 `quantlab download …` 或 `quantlab download-all`。")
        st.stop()

    names = load_names(root)
    if not names:
        with st.spinner("首次启动，正在构建名称库…"):
            names = build_names(dm)

    def label(s: str) -> str:
        nm = names.get(s, "")
        return f"{s.split(':', 1)[1]}　{nm}".strip() if nm and nm != s.split(':', 1)[1] else s

    options = sorted(set(cached) | set(names))   # 含未缓存（选中将自动下载）
    st.session_state.setdefault("sym", "CN:600519" if "CN:600519" in options else options[0])

    def _pick(s: str) -> None:
        st.session_state.sym = s

    # ---------- 侧栏 ----------
    sb = st.sidebar
    sb.header("🔎 选择标的")
    sb.caption(f"本地已缓存 {len(cached)} 只，可按代码或名称搜索")

    favs = [f for f in load_favorites(root) if f in options]
    if favs:
        sb.subheader("⭐ 我的收藏")
        for f in favs:
            sb.button(label(f), key=f"fav_{f}", on_click=_pick, args=(f,), use_container_width=True)

    if dm.cfg.watchlists:
        with sb.expander("📁 主题池"):
            for theme, syms in dm.cfg.watchlists.items():
                avail = [s.key for s in syms if s.key in options]
                if avail:
                    st.markdown(f"**{theme}**")
                    for s in avail:
                        st.button(label(s), key=f"wl_{theme}_{s}", on_click=_pick, args=(s,),
                                  use_container_width=True)

    sb.divider()
    symbol = sb.selectbox("搜索 / 选择", options, format_func=label, key="sym")
    is_fav = symbol in load_favorites(root)
    sb.button("💔 取消收藏" if is_fav else "⭐ 收藏当前", on_click=lambda: toggle_favorite(root, symbol),
              use_container_width=True)

    sb.divider()
    adjust = Adjust(sb.selectbox("复权", ["qfq", "hfq", "raw"], index=0))
    freq = Freq(sb.selectbox("周期", ["1d", "1w", "1M"], index=0,
                             format_func={"1d": "日线", "1w": "周线", "1M": "月线"}.get))
    overlays = sb.multiselect("指标叠加", DEFAULT_INDICATORS, default=["ma5", "ma20"])

    # ---------- 取数 ----------
    try:
        with st.spinner("下载/读取数据中…（未缓存的标的会自动联网下载）"):
            df = add_indicators(dm.history(symbol, adjust=adjust, freq=freq))
    except Exception as e:  # noqa: BLE001
        st.error(f"取数失败：{e}")
        st.stop()

    st.subheader(f"{label(symbol)}　`{symbol}`")

    def dl(fig, name: str, key: str) -> None:
        st.download_button("⬇ 下载图表(HTML，可交互)", fig.to_html(), file_name=f"{name}.html",
                           mime="text/html", key=key)

    tab_q, tab_bt, tab_p, tab_cmp = st.tabs(["📈 行情", "🔬 回测", "🎲 条件概率", "📊 多标的对比"])

    # ===== 行情 =====
    with tab_q:
        fig = plot_candles(df, overlays, title=label(symbol))
        render_xzoom(fig, 560)
        render_xzoom(plot_volume(df), 240)
        c1, c2 = st.columns(2)
        with c1:
            dl(fig, f"{symbol}_kline", "dl_k")
        with c2:
            st.download_button("⬇ 下载数据(CSV)", df.to_csv().encode("utf-8-sig"),
                               file_name=f"{symbol}.csv", mime="text/csv")

    # ===== 回测 =====
    with tab_bt:
        c1, c2, c3 = st.columns(3)
        which = c1.selectbox("策略", ["dualma", "rsi"],
                             format_func={"dualma": "双均线", "rsi": "RSI均值回归"}.get)
        cost = c2.number_input("成本(基点)", 0.0, 50.0, 5.0, 1.0)
        if which == "dualma":
            fast = c3.number_input("快线", 2, 60, 5)
            slow = c3.number_input("慢线", 5, 250, 20)
            strat = DualMAStrategy(int(fast), int(slow))
        else:
            strat = RsiReversionStrategy()
        res = Backtester(cost).run(df, strat)
        m = st.columns(5)
        m[0].metric("总收益", f"{res.total_return:.1%}")
        m[1].metric("年化", f"{res.cagr:.1%}")
        m[2].metric("夏普", f"{res.sharpe:.2f}")
        m[3].metric("最大回撤", f"{res.max_drawdown:.1%}")
        m[4].metric("买入持有", f"{res.buy_hold.iloc[-1] - 1:.1%}")
        eqfig = plot_equity(res)
        render_xzoom(eqfig, 460)
        render_xzoom(plot_drawdown(res), 280)
        dl(eqfig, f"{symbol}_equity", "dl_eq")

    # ===== 条件概率 =====
    with tab_p:
        c1, c2, c3 = st.columns(3)
        pct = c1.slider("单日跌幅阈值", 0.005, 0.05, 0.015, 0.005, format="%.3f")
        nd = c2.slider("连跌天数", 1, 5, 1)
        fwd = c3.slider("看未来几日", 1, 10, 1)
        extra_rsi = st.checkbox("叠加 RSI<30")
        cond = drop_gt(pct)
        if nd > 1:
            cond = cond & n_down_days(nd)
        if extra_rsi:
            cond = cond & rsi_lt(30)
        try:
            r = probability(df, cond, fwd, dm.cfg.stats_min_samples, symbol)
            pos = build_sizer(dm.cfg).size(r)
            m = st.columns(5)
            m[0].metric("上涨概率", f"{r.p_up:.1%}")
            m[1].metric("基准率", f"{r.base_rate:.1%}")
            m[2].metric("edge", f"{r.edge:+.1%}", delta=f"{r.edge:+.1%}")
            m[3].metric("样本/盈亏比", f"N={r.n} / {r.payoff:.2f}")
            m[4].metric("建议仓位", f"{pos:.0%}")
            st.caption(f"95% 置信区间 {r.ci_low:.1%}~{r.ci_high:.1%}　平均MAE {r.mae:.1%}　"
                       f"{'✅ 样本充足' if r.reliable else '⚠️ 样本不足，不可靠'}")
            pfig = plot_probability(r)
            _chart(pfig)
            _chart(plot_return_hist(df, cond, fwd))
            dl(pfig, f"{symbol}_prob", "dl_p")
        except InsufficientData:
            st.info("该条件下样本为 0，换个条件试试。")

    # ===== 多标的对比 =====
    with tab_cmp:
        picks = st.multiselect("选择对比标的（归一化走势）", options, format_func=label,
                               default=[symbol] + favs[:3])
        if picks:
            sm = {}
            for s in picks:
                try:
                    sm[label(s)] = dm.history(s, adjust=adjust, freq=freq)[CLOSE]
                except Exception:  # noqa: BLE001
                    pass
            if sm:
                cfig = plot_compare(sm)
                render_xzoom(cfig, 480)
                dl(cfig, "compare", "dl_cmp")

    st.caption("💡 图表右上角 📷 可直接存 PNG；或用上方按钮下载可交互 HTML。仅供研究，非投资建议。")


if __name__ == "__main__":
    main()
