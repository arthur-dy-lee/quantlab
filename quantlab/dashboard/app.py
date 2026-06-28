"""QuantLab 本地中文看板（详细设计 §10.3）。

运行：``streamlit run quantlab/dashboard/app.py``（需 ``pip install -e '.[dashboard]'``）。
端口固定为 8110（见 ``.streamlit/config.toml``），访问 http://localhost:8110 。
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
        plot_allocation_backtest, plot_candles, plot_compare, plot_drawdown,
        plot_equity, plot_probability, plot_return_hist, plot_securitization,
        plot_volume,
    )

    st.set_page_config(page_title="QuantLab 量化看板", page_icon="📊", layout="wide")
    st.markdown("<style>#MainMenu{visibility:hidden}footer{visibility:hidden}</style>",
                unsafe_allow_html=True)
    st.title("📊 QuantLab 量化看板")

    import streamlit.components.v1 as components

    # 滚轮缩放 + 去 logo；双击复位到全量区间
    _CFG = {"scrollZoom": True, "displaylogo": False, "doubleClick": "reset"}

    def _chart(fig):
        st.plotly_chart(fig, use_container_width=True, config=_CFG)

    # 时间序列交互（看盘网站/同花顺手感）：
    #  · 拖拽=平移时间轴（dragmode 在 charts.style_timeseries 里设 pan）
    #  · 滚轮 / Cmd(Ctrl) +、- = 缩放；Cmd(Ctrl)+0 复位；← → = 平移（需先点一下图聚焦）
    #  · X 区间一变，Y 轴按可见区间自适应（同花顺看一段就贴合一段）
    _INTERACT_JS = """
    var gd=document.getElementById('{plot_id}');
    function _xr(){
      var xa=gd._fullLayout&&gd._fullLayout.xaxis;
      if(xa&&xa.range&&xa.range.length===2)
        return [new Date(xa.range[0]).getTime(), new Date(xa.range[1]).getTime()];
      var lo=Infinity,hi=-Infinity;
      (gd.data||[]).forEach(function(t){var xs=t.x; if(!xs||!xs.length) return;
        var a=new Date(xs[0]).getTime(), b=new Date(xs[xs.length-1]).getTime();
        if(a<lo)lo=a; if(b>hi)hi=b;});
      return [lo,hi];
    }
    function _fitY(){
      var r=_xr(), x0=r[0], x1=r[1], lo=Infinity, hi=-Infinity;
      (gd.data||[]).forEach(function(t){var xs=t.x; if(!xs) return;
        for(var i=0;i<xs.length;i++){
          var v=new Date(xs[i]).getTime(); if(v<x0||v>x1) continue;
          if(t.type==='candlestick'){ if(t.low[i]<lo)lo=t.low[i]; if(t.high[i]>hi)hi=t.high[i]; }
          else if(t.y){ var y=t.y[i]; if(y<lo)lo=y; if(y>hi)hi=y; }
        }});
      if(lo<hi){ var p=(hi-lo)*0.06; Plotly.relayout(gd,{'yaxis.range':[lo-p,hi+p]}); }
    }
    function _zoom(f){ var r=_xr(), c=(r[0]+r[1])/2, h=(r[1]-r[0])/2*f;
      Plotly.relayout(gd,{'xaxis.range':[c-h,c+h]}).then(_fitY); }
    function _pan(fr){ var r=_xr(), w=(r[1]-r[0])*fr;
      Plotly.relayout(gd,{'xaxis.range':[r[0]+w,r[1]+w]}).then(_fitY); }
    gd.on('plotly_relayout', function(e){ if(('xaxis.range[0]' in e)||e['xaxis.autorange']) setTimeout(_fitY,30); });
    gd.setAttribute('tabindex','0'); gd.style.outline='none';
    gd.addEventListener('keydown', function(ev){
      var m=ev.ctrlKey||ev.metaKey;
      if(m&&(ev.key==='='||ev.key==='+')){ ev.preventDefault(); _zoom(0.8); }
      else if(m&&(ev.key==='-'||ev.key==='_')){ ev.preventDefault(); _zoom(1.25); }
      else if(m&&ev.key==='0'){ ev.preventDefault(); Plotly.relayout(gd,{'xaxis.autorange':true,'yaxis.autorange':true}); }
      else if(ev.key==='ArrowLeft'){ ev.preventDefault(); _pan(-0.15); }
      else if(ev.key==='ArrowRight'){ ev.preventDefault(); _pan(0.15); }
    });
    """

    def render_xzoom(fig, height=520):
        # 图自身高度跟 iframe 一致，否则默认 450px 会被矮 iframe 截掉底部 X 轴
        fig.update_layout(height=height, margin=dict(l=40, r=20, t=40, b=44))
        html = fig.to_html(include_plotlyjs="cdn", full_html=True, config=_CFG,
                           post_script=_INTERACT_JS)
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
        st.download_button("⬇ 下载图表(HTML，可交互)", fig.to_html(config=_CFG),
                           file_name=f"{name}.html", mime="text/html", key=key)

    tab_q, tab_bt, tab_p, tab_cmp, tab_sec, tab_th = st.tabs(
        ["📈 行情", "🔬 回测", "🎲 条件概率", "📊 多标的对比", "📈 证券化率", "🌡️ 温度计·加减仓"])

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

    # ===== 证券化率 / 巴菲特指标（与所选标的无关，全局宏观）=====
    with tab_sec:
        st.caption("证券化率 ＝ 股市总市值 ÷ GDP（巴菲特指标）。"
                   "中国每日(akshare)、美国季度(FRED)；首次或刷新时联网。")
        refresh = st.button("🔄 联网刷新宏观数据", key="sec_refresh")
        try:
            from quantlab.datasources.macro_source import (
                china_securitization, historical_percentile, us_securitization,
            )
            with st.spinner("读取/计算证券化率…"):
                cn = china_securitization(dm.cfg.data_root, refresh=refresh)
                us = us_securitization(dm.cfg.data_root, refresh=refresh)
                cn_pct = historical_percentile(cn["ratio"])
            cn_last, us_last = cn.iloc[-1], us.iloc[-1]
            m = st.columns(4)
            m[0].metric("中国证券化率", f"{cn_last['ratio']:.1f}%",
                        help=f"截至 {cn.index[-1].date()}　总市值 {cn_last['mktcap_yi'] / 1e4:.1f} 万亿元")
            m[1].metric("中国历史分位", f"{cn_pct.iloc[-1]:.0f}%", help="在自身历史中的位置，越高越贵")
            m[2].metric("美国证券化率", f"{us_last['ratio']:.0f}%", help=f"截至 {us.index[-1].date()}")
            m[3].metric("美 ÷ 中 倍数", f"{us_last['ratio'] / cn_last['ratio']:.1f}×")
            secfig = plot_securitization(cn["ratio"], us["ratio"], cn_pct)
            render_xzoom(secfig, 520)
            dl(secfig, "securitization", "dl_sec")
        except Exception as e:  # noqa: BLE001
            st.error(f"宏观数据获取失败（首次需联网）：{e}")

    # ===== 市场温度计 / 加减仓（全局宏观，与所选标的无关）=====
    with tab_th:
        st.caption("市场温度计 ＝ 中位 PE/PB + ERP + 两融 合成的净温度；决策层把"
                   "「净温度档 × 拐点」所处区间的历史前向收益映射成**建议目标仓位%**。"
                   "诚实提示：**不跑赢买入持有**，价值在控回撤与纪律，最稳信号是抄极冷底。")
        refresh = st.button("🔄 联网刷新温度与指数", key="th_refresh")
        try:
            from quantlab.signals import allocator as al
            with st.spinner("读取/计算温度与区间前向收益…"):
                adv = al.recommend_position("CN", refresh=refresh, data_root=dm.cfg.data_root)
                eq, mt = al.backtest_allocation("CN", data_root=dm.cfg.data_root)
            m = st.columns(4)
            m[0].metric("净温度", f"{adv.net:+.0f}",
                        help=f"顶部 {adv.top:.0f} / 底部 {adv.bottom:.0f}　截至 {adv.date.date()}")
            m[1].metric("所处区间", adv.regime, help=f"近20日 {adv.momentum:+.1f} → {adv.turning}")
            m[2].metric("建议目标仓位", f"{adv.target:.0f}%", help="现仓高于则减、低于则加")
            m[3].metric(f"同区间未来{adv.horizon}日胜率", f"{adv.win_rate:.0%}",
                        help=f"n={adv.n}　均值 {adv.mean_fwd:+.1%}　置信度 {adv.confidence}")
            st.info(f"▶ {adv.verdict}")
            st.caption(f"走查回测(沪深300 因果)：温度择仓 CAGR {mt['strat_cagr']:.1%} / "
                       f"回撤 {mt['strat_maxdd']:.0%} / 夏普 {mt['strat_sharpe']:.2f}　vs　"
                       f"买入持有 CAGR {mt['bh_cagr']:.1%} / 回撤 {mt['bh_maxdd']:.0%} / "
                       f"夏普 {mt['bh_sharpe']:.2f}")
            thfig = plot_allocation_backtest(eq)
            render_xzoom(thfig, 520)
            dl(thfig, "thermometer_allocation", "dl_th")
        except Exception as e:  # noqa: BLE001
            st.error(f"温度计数据获取失败（首次需联网取指数价格）：{e}")

    st.caption(
        "🖱️ 操作：**拖拽**左右移动看不同时段；**滚轮**或 **Cmd/Ctrl +、-** 缩放；"
        "**Cmd/Ctrl+0**（或双击）复位；点一下图后可用 **← →** 平移。鼠标移动有十字光标读价。"
        "　右上角 📷 存 PNG，上方按钮下载可交互 HTML。仅供研究，非投资建议。"
    )


if __name__ == "__main__":
    main()
