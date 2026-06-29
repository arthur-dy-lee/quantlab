#!/usr/bin/env python
"""兴登堡凶兆「对A股不起作用」一文的配图 + 逐日证据表。

输出 4 张图到 research/assets/，并把逐日证据 markdown 表写到 stdout/文件，供文章引用：
  A 两大顶证据(2007/2015 新高新低逐日)    兴登堡凶兆_两大顶证据.png
  B 全历史时间线(凶兆 vs 真崩盘)          兴登堡凶兆_全历史时间线.png
  C 有效性(前向收益 + 崩盘捕获)           兴登堡凶兆_有效性.png
  D 新高×新低散点(危险方框 + 两大顶位置)  兴登堡凶兆_新高新低散点.png

用法：python scripts/hindenburg_rebuttal_plots.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from quantlab.core import forward_return, mae
from quantlab.datasources.breadth_source import cn_breadth
from quantlab.datasources import valuation_source as vs
from quantlab.signals import hindenburg as hb

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False
ASSETS = Path("research/assets")
GREEN, RED, GREY, BLUE = "#1a9850", "#d73027", "#888", "#2166ac"


def _frame():
    b = cn_breadth()
    px = vs.cn_index_ohlc("000001")
    o = hb.omen_table(px, b)
    o["nh"] = 100 * o["nh_pct"]
    o["nl"] = 100 * o["nl_pct"]
    o["close"] = px["close"].reindex(o.index).ffill()
    return b, px, o


# ── A 两大顶证据 ──────────────────────────────────────────────────────────
def chart_tops(o):
    # (绘图上下文窗口, 报告点名的触发子窗口, 报告称次数, 标题)
    wins = [("2007-07-01", "2007-12-31", "2007-08-01", "2007-10-31", 6, "2007 年 6124 大顶"),
            ("2015-03-01", "2015-08-31", "2015-05-01", "2015-06-30", 8, "2015 年 5178 杠杆牛顶")]
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), gridspec_kw={"hspace": 0.30})
    for ax, (s, e, cs, ce, claim, title) in zip(axes, wins):
        w = o.loc[s:e]
        ax.fill_between(w.index, w["nh"], 0, color=GREEN, alpha=0.55, label="创新高股占比%")
        ax.fill_between(w.index, w["nl"], 0, color=RED, alpha=0.65, label="创新低股占比%")
        ax.axhline(2.2, color="k", ls="--", lw=1, label="2.2% 触发阈值")
        ax.axvspan(pd.Timestamp(cs), pd.Timestamp(ce), color=BLUE, alpha=0.10)
        ax.set_ylabel("占合格正股 %", fontsize=10)
        ax.set_title(f"{title}（报告称此蓝区凶兆触发 {claim} 次）", fontsize=12)
        cw = o.loc[cs:ce]                       # 只按报告点名的窗口统计
        ax.text(0.015, 0.93,
                f"报告点名窗口 {cs}~{ce}：实测凶兆日 = {int(cw['omen'].sum())} 次　|　"
                f"该窗口新低峰值 = {cw['nl'].max():.2f}%（远不及 2.2%）",
                transform=ax.transAxes, fontsize=10.5, color=RED, va="top",
                bbox=dict(boxstyle="round", fc="#fff3cd", ec=RED))
        axp = ax.twinx()
        axp.plot(w.index, w["close"], color="#333", lw=1.2, label="上证综指(右)")
        axp.set_ylabel("上证综指", fontsize=10)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = axp.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=9, ncol=2)
    fig.suptitle("证据 A｜两大顶部「新低」几乎为零 → 第①条（新高&新低均≥2.2%）数学上无法满足",
                 fontsize=14, y=0.98)
    fig.savefig(ASSETS / "兴登堡凶兆_两大顶证据.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


# ── B 全历史时间线 ────────────────────────────────────────────────────────
def chart_timeline(o):
    ep = hb.episodes(o)
    crashes = [("2008-01-01", "2008-11-04", "08 危机 −70%"),
               ("2015-06-15", "2016-01-28", "15 股灾 −47%"),
               ("2018-01-29", "2019-01-04", "18 熊市 −31%"),
               ("2021-12-13", "2022-04-26", "22 杀跌 −25%")]
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(o.index, o["close"], color="#333", lw=1.0, label="上证综指")
    ax.set_yscale("log")
    for s, e, lab in crashes:
        ax.axvspan(pd.Timestamp(s), pd.Timestamp(e), color=RED, alpha=0.12)
        mid = o.loc[s:e]
        if len(mid):
            ax.text(mid.index[len(mid) // 2], o["close"].max() * 0.95, lab,
                    color=RED, fontsize=9, ha="center", va="top")
    for d in ep:
        ax.axvline(d, color=BLUE, lw=1.4, alpha=0.8)
    ax.axvline(ep[0], color=BLUE, lw=1.4, alpha=0.8, label="凶兆确认事件")
    ax.set_title("证据 B｜10 个凶兆事件（蓝线）全部躲开了 A股 4 次真崩盘（红区）；"
                 "信号扎堆在 2017/2020-21/2023 的「分化慢牛」而非顶部", fontsize=12)
    ax.legend(loc="lower right", fontsize=10)
    ax.set_ylabel("上证综指（对数轴）")
    fig.savefig(ASSETS / "兴登堡凶兆_全历史时间线.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


# ── C 有效性：前向收益 + 崩盘捕获 ─────────────────────────────────────────
def chart_effectiveness(o, px):
    active = o["active"].reindex(px.index).fillna(False)
    uptrend = o["uptrend"].reindex(px.index).fillna(False)
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(14, 5.5), gridspec_kw={"wspace": 0.25})

    hs = [20, 60, 120]
    a_mean, u_mean = [], []
    for h in hs:
        fwd = forward_return(px, h)
        a_mean.append(100 * fwd[active & fwd.notna()].mean())
        u_mean.append(100 * fwd[uptrend & fwd.notna()].mean())
    x = np.arange(len(hs)); ww = 0.36
    axL.bar(x - ww / 2, a_mean, ww, color=RED, label="凶兆活跃期")
    axL.bar(x + ww / 2, u_mean, ww, color=GREY, label="上升趋势基准")
    for i, (av, uv) in enumerate(zip(a_mean, u_mean)):
        axL.text(i - ww / 2, av, f"{av:+.1f}%", ha="center", va="bottom", fontsize=9, color=RED)
        axL.text(i + ww / 2, uv, f"{uv:+.1f}%", ha="center", va="bottom", fontsize=9)
    axL.set_xticks(x); axL.set_xticklabels([f"{h}日" for h in hs])
    axL.set_ylabel("上证综指前向收益均值 %")
    axL.set_title("C1 前向收益：活跃期系统性跑输常态（“涨不动”）", fontsize=11)
    axL.legend(fontsize=9); axL.axhline(0, color="k", lw=0.6)

    dd = mae(px, 60)
    a, u, al = dd[active & dd.notna()], dd[uptrend & dd.notna()], dd[dd.notna()]
    thr = [-0.10, -0.15, -0.20]
    pa = [100 * (a < t).mean() for t in thr]
    pu = [100 * (u < t).mean() for t in thr]
    pl = [100 * (al < t).mean() for t in thr]
    x = np.arange(len(thr)); ww = 0.27
    axR.bar(x - ww, pa, ww, color=RED, label="凶兆活跃期")
    axR.bar(x, pu, ww, color=GREY, label="上升趋势基准")
    axR.bar(x + ww, pl, ww, color="#bbb", label="全样本")
    for i in range(len(thr)):
        axR.text(i - ww, pa[i], f"{pa[i]:.0f}%", ha="center", va="bottom", fontsize=9, color=RED)
        axR.text(i, pu[i], f"{pu[i]:.0f}%", ha="center", va="bottom", fontsize=9)
    axR.set_xticks(x); axR.set_xticklabels([f"跌破{int(-t*100)}%" for t in thr])
    axR.set_ylabel("P(未来60日最大回撤 < 阈值) %")
    axR.set_title("C2 崩盘捕获：活跃期反而最不易大跌（卖点落空）", fontsize=11)
    axR.legend(fontsize=9)
    fig.suptitle("证据 C｜“92% 有效”的反面：信号活跃期前向收益更低、却更不容易发生大回撤", fontsize=13)
    fig.savefig(ASSETS / "兴登堡凶兆_有效性.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


# ── D 新高×新低散点 ───────────────────────────────────────────────────────
def chart_scatter(o):
    d = o.dropna(subset=["nh", "nl"])
    fig, ax = plt.subplots(figsize=(9, 8))
    normal = ~d["omen"]
    ax.scatter(d.loc[normal, "nl"], d.loc[normal, "nh"], s=6, color=GREY, alpha=0.35, label="普通交易日")
    ax.scatter(d.loc[d["omen"], "nl"], d.loc[d["omen"], "nh"], s=18, color=RED, label="凶兆日")
    # 两大顶位置
    for dt, name in [("2007-10-16", "2007 大顶"), ("2015-06-12", "2015 顶")]:
        near = d.loc[:dt].tail(1)
        if len(near):
            ax.scatter(near["nl"], near["nh"], s=140, marker="*", color=BLUE, zorder=5)
            ax.annotate(name, (near["nl"].iloc[0], near["nh"].iloc[0]),
                        textcoords="offset points", xytext=(8, 4), color=BLUE, fontsize=10)
    ax.axvline(2.2, color="k", ls="--", lw=1)
    ax.axhline(2.2, color="k", ls="--", lw=1)
    ax.axvspan(2.2, 50, ymin=2.2 / 50, color="orange", alpha=0.10)
    ax.text(26, 47, "兴登堡“分裂”区\n(新高&新低均≥2.2%)", color="#b8860b", fontsize=10, ha="center")
    ax.set_xlim(-0.5, 50); ax.set_ylim(-0.5, 50)
    ax.set_xlabel("当日创新低股占比 %"); ax.set_ylabel("当日创新高股占比 %")
    ax.set_title("证据 D｜A股的日子几乎都贴着坐标轴（非高即低，少有“双高分裂”）\n两大顶★落在左上角（全员新高、零新低）——根本进不了危险区", fontsize=12)
    ax.legend(loc="upper right", fontsize=10)
    fig.savefig(ASSETS / "兴登堡凶兆_新高新低散点.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


# ── 逐日证据表（markdown）────────────────────────────────────────────────
def daily_table(o, start, end) -> str:
    w = o.loc[start:end]
    lines = ["| 日期 | 上证 | 新高% | 新低% | McClellan | ①双高 | ②高≤2×低 | ③上升 | ④McC<0 | 凶兆 |",
             "|------|-----:|------:|------:|----------:|:---:|:---:|:---:|:---:|:---:|"]
    yes = lambda x: "✓" if bool(x) else "·"
    for dt, r in w.iterrows():
        lines.append(f"| {dt.date()} | {r['close']:.0f} | {r['nh']:.1f} | {r['nl']:.2f} | "
                     f"{r['mcclellan']:+.0f} | {yes(r['cond1_split'])} | {yes(r['cond2_lows'])} | "
                     f"{yes(r['cond3_uptrend'])} | {yes(r['cond4_mcclellan'])} | {'🔴' if r['omen'] else '·'} |")
    return "\n".join(lines)


def main():
    b, px, o = _frame()
    chart_tops(o); chart_timeline(o); chart_effectiveness(o, px); chart_scatter(o)
    print("图表已输出 research/assets/。\n")
    out = Path("/private/tmp/claude-501/-Users-arthur-lee-codes-quantlab-research/"
               "db63a722-02c0-4f2a-af03-87180bd7c5a8/scratchpad/daily_tables.md")
    txt = []
    txt.append("### 2015-05~06 全部交易日（报告称“触发8次”）\n")
    txt.append(daily_table(o, "2015-05-01", "2015-06-30"))
    txt.append(f"\n\n小结：该窗口共 {len(o.loc['2015-05-01':'2015-06-30'])} 个交易日，"
               f"凶兆日 = {int(o.loc['2015-05-01':'2015-06-30','omen'].sum())} 次，"
               f"第①条满足 0 天，新低占比峰值 {o.loc['2015-05-01':'2015-06-30','nl'].max():.2f}%。\n")
    txt.append("\n### 2007-08~10 关键交易日（报告称“触发6次”，抽样）\n")
    txt.append(daily_table(o, "2007-09-15", "2007-10-31"))
    txt.append(f"\n\n小结：2007-08~10 全窗口凶兆日 = {int(o.loc['2007-08-01':'2007-10-31','omen'].sum())} 次，"
               f"新低占比峰值 {o.loc['2007-08-01':'2007-10-31','nl'].max():.2f}%。\n")
    # 关键统计供正文引用
    active = o["active"].reindex(px.index).fillna(False)
    uptrend = o["uptrend"].reindex(px.index).fillna(False)
    dd = mae(px, 60)
    txt.append("\n### 正文引用统计\n")
    for h in (20, 60, 120):
        fwd = forward_return(px, h)
        txt.append(f"- {h}日前向: 活跃 {100*fwd[active&fwd.notna()].mean():+.1f}% / "
                   f"基准 {100*fwd[uptrend&fwd.notna()].mean():+.1f}%")
    txt.append(f"- P(60日跌>10%): 活跃 {100*(dd[active&dd.notna()]<-0.10).mean():.0f}% / "
               f"基准 {100*(dd[uptrend&dd.notna()]<-0.10).mean():.0f}% / 全样本 {100*(dd[dd.notna()]<-0.10).mean():.0f}%")
    out.write_text("\n".join(txt), encoding="utf-8")
    print(f"逐日表与统计已写 {out}")
    print("\n".join(txt[-6:]))


if __name__ == "__main__":
    main()
