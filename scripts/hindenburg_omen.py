#!/usr/bin/env python
"""兴登堡凶兆 A股验证：是否「匹配 + 管用」。详见 research/兴登堡凶兆_A股适配与验证.md。

四块输出：
  ① 全市场宽度概览（生存者偏差/口径自检）
  ② 事件清单——每个确认事件后指数 60 日最大回撤 / 60 日收益，对照已知 A股顶部
  ③ 事件研究——凶兆「活跃」日 vs **上升趋势基准** 的前向收益/回撤（关键：是否比"市场在涨"多给信息）
  ④ 多指数稳健性——同口径在上证综指/沪深300/中证500/中证全指上的方向是否一致

用法：python scripts/hindenburg_omen.py [--index 000001] [--threshold 0.022]
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from quantlab.core import forward_return, mae
from quantlab.datasources.breadth_source import cn_breadth
from quantlab.datasources import valuation_source as vs
from quantlab.signals import hindenburg as hb

INDICES = {"上证综指": "000001", "沪深300": "000300", "中证500": "000905", "中证全指": "000985"}
HORIZONS = (20, 60, 120)
# 已知 A股顶部 / 重要拐点（用于对照事件是否"踩点"）
KNOWN_TOPS = {
    "2007-10": "6124 大顶", "2009-08": "3478 反弹顶", "2010-11": "3186 顶",
    "2015-06": "5178 杠杆牛顶", "2018-01": "3587 顶(随后熊)", "2021-02": "核心资产顶(沪深300)",
    "2021-09": "中证500/小盘顶", "2023-05": "中特估/AI 顶", "2024-10": "924 行情急涨",
}


def _cond_stats(fwd: pd.Series, mask: pd.Series, base_mask: pd.Series) -> dict:
    """条件样本 vs 基准样本的前向收益对比。"""
    c = fwd[mask & fwd.notna()]
    base = fwd[base_mask & fwd.notna()]
    return {
        "n": len(c), "mean": c.mean(), "median": c.median(), "p_neg": (c < 0).mean(),
        "base_mean": base.mean(), "base_median": base.median(), "base_p_neg": (base < 0).mean(),
    }


def section_overview(b: pd.DataFrame) -> None:
    print("=" * 74)
    print("  ① 全市场宽度概览（口径自检）")
    print("=" * 74)
    bb = b[b["qualified"] >= hb.MIN_QUALIFIED]
    nh = 100 * bb["new_high"] / bb["qualified"]
    nl = 100 * bb["new_low"] / bb["qualified"]
    print(f"样本: {bb.index.min().date()} → {bb.index.max().date()}  "
          f"合格正股 {int(bb['qualified'].iloc[0])} → {int(bb['qualified'].iloc[-1])}")
    print(f"新高% 分位: 50/90/99 = {nh.quantile(.5):.1f}/{nh.quantile(.9):.1f}/{nh.quantile(.99):.1f}")
    print(f"新低% 分位: 50/90/99 = {nl.quantile(.5):.1f}/{nl.quantile(.9):.1f}/{nl.quantile(.99):.1f}")
    print("注：本地正股集合仅含当前在市者→历史新低被低估(生存者偏差)，对底部偏保守。")


def section_episodes(o: pd.DataFrame, px: pd.DataFrame, name: str) -> None:
    print("\n" + "=" * 74)
    print(f"  ② 确认事件清单（趋势判定指数={name}；事件后 60 交易日表现）")
    print("=" * 74)
    ep = hb.episodes(o)
    if len(ep) == 0:
        print("无确认事件。")
        return
    fwd60 = forward_return(px, 60)
    dd60 = mae(px, 60)  # 未来60日相对当日的最大不利回撤(≤0)
    print(f"{'确认日':12s}{'上证点位':>9s}{'后60日收益':>11s}{'后60日最大回撤':>14s}  对照")
    for d in ep:
        if d not in px.index:
            d2 = px.index[px.index.get_indexer([d], method="nearest")[0]]
        else:
            d2 = d
        lvl = px.loc[d2, "close"]
        r = fwd60.get(d2, np.nan)
        dd = dd60.get(d2, np.nan)
        ym = f"{d.year}-{d.month:02d}"
        tag = KNOWN_TOPS.get(ym, "")
        rs = f"{r:+.1%}" if pd.notna(r) else "n/a"
        dds = f"{dd:.1%}" if pd.notna(dd) else "n/a"
        print(f"{str(d.date()):12s}{lvl:>9.0f}{rs:>11s}{dds:>14s}  {tag}")
    print(f"\n事件数 {len(ep)}。负收益事件占比 "
          f"{np.mean([forward_return(px,60).get(px.index[px.index.get_indexer([d],method='nearest')[0]], np.nan) < 0 for d in ep]):.0%}")


def section_event_study(o: pd.DataFrame, px: pd.DataFrame, name: str) -> None:
    print("\n" + "=" * 74)
    print(f"  ③ 事件研究：凶兆活跃日 vs 上升趋势基准（{name}）")
    print("=" * 74)
    active = o["active"].reindex(px.index).fillna(False)
    uptrend = o["uptrend"].reindex(px.index).fillna(False)  # 公平基准=同处上升趋势
    print(f"{'前向':>5s} | {'活跃 n':>7s}{'均值':>8s}{'中位':>8s}{'胜<0':>7s} | "
          f"{'上升趋势基准 均值':>14s}{'中位':>8s}{'<0%':>7s}")
    for h in HORIZONS:
        fwd = forward_return(px, h)
        s = _cond_stats(fwd, active, uptrend)
        print(f"{h:4d}日 | {s['n']:7d}{s['mean']:+8.1%}{s['median']:+8.1%}{s['p_neg']:7.0%} | "
              f"{s['base_mean']:+14.1%}{s['base_median']:+8.1%}{s['base_p_neg']:7.0%}")
    # 下行尾部：未来60日最大回撤
    dd = mae(px, 60)
    a = dd[active & dd.notna()]
    u = dd[uptrend & dd.notna()]
    print(f"未来60日最大回撤  活跃: 均值{a.mean():.1%} / P(<-10%)={ (a<-0.10).mean():.0%}"
          f"   |  趋势基准: 均值{u.mean():.1%} / P(<-10%)={(u<-0.10).mean():.0%}")


def section_crash_capture(o: pd.DataFrame, px: pd.DataFrame, name: str) -> None:
    """是否真能预告崩盘：对比 P(未来60日跌>X | 活跃) vs 基准/全样本。这是兴登堡的核心卖点。"""
    print("\n" + "=" * 74)
    print(f"  ⑤ 崩盘捕获力：P(未来60日最大回撤 < 阈值 | 条件)（{name}）")
    print("=" * 74)
    dd = mae(px, 60)
    active = o["active"].reindex(px.index).fillna(False) & dd.notna()
    uptrend = o["uptrend"].reindex(px.index).fillna(False) & dd.notna()
    alld = dd.notna()
    print(f"{'回撤阈值':>8s}{'| 活跃期':>10s}{'上升趋势基准':>12s}{'全样本':>9s}")
    for thr in (-0.10, -0.15, -0.20):
        print(f"{thr:>8.0%}{(dd[active]<thr).mean():>10.0%}{(dd[uptrend]<thr).mean():>12.0%}{(dd[alld]<thr).mean():>9.0%}")
    print("若'活跃期'列不显著高于基准列 → 凶兆并不预告 A股崩盘（卖点落空）。")


def section_robustness(b: pd.DataFrame, threshold: float) -> None:
    print("\n" + "=" * 74)
    print("  ④ 多指数稳健性（活跃日 60 日前向收益 − 同指数上升趋势基准）")
    print("=" * 74)
    print(f"{'指数':10s}{'事件数':>6s}{'活跃日':>7s}{'活跃60日':>9s}{'趋势基准':>9s}{'超额':>8s}")
    for nm, code in INDICES.items():
        px = vs.cn_index_ohlc(code)
        o = hb.omen_table(px, b, threshold=threshold)
        active = o["active"].reindex(px.index).fillna(False)
        uptrend = o["uptrend"].reindex(px.index).fillna(False)
        fwd = forward_return(px, 60)
        ca, cu = fwd[active & fwd.notna()], fwd[uptrend & fwd.notna()]
        ne = len(hb.episodes(o))
        excess = ca.mean() - cu.mean()
        print(f"{nm:10s}{ne:>6d}{active.sum():>7d}{ca.mean():>+9.1%}{cu.mean():>+9.1%}{excess:>+8.1%}")
    print("\n超额<0 = 凶兆活跃期收益低于'同处上升趋势'的常态 → 信号有效（择时减仓有据）。")


def main(index_code: str, threshold: float) -> None:
    b = cn_breadth()
    name = {v: k for k, v in INDICES.items()}.get(index_code, index_code)
    px = vs.cn_index_ohlc(index_code)
    o = hb.omen_table(px, b, threshold=threshold)

    section_overview(b)
    section_episodes(o, px, name)
    section_event_study(o, px, name)
    section_crash_capture(o, px, name)
    section_robustness(b, threshold)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="000001", help="趋势判定/主评估指数(默认上证综指)")
    ap.add_argument("--threshold", type=float, default=hb.THRESHOLD, help="新高/新低占比阈值")
    a = ap.parse_args()
    main(a.index, a.threshold)
