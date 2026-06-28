#!/usr/bin/env python
"""市场温度计 v1 历史回看图。

顶部/底部/净温度叠加上证综指走势，肉眼验收历史大顶大底。
输出 research/assets/市场温度计_历史回看.png。

用法：python scripts/market_thermometer_plot.py [--refresh]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from quantlab.signals import thermometer as th

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False

# 标注用的历史大顶/大底（肉眼验收锚点）
ANCHORS = [
    ("2007-10", "07年6124顶", "top"),
    ("2015-06", "15年杠杆牛顶", "top"),
    ("2021-02", "21年抱团顶", "top"),
    ("2008-11", "08年危机底", "bottom"),
    ("2018-12", "18年熊底", "bottom"),
    ("2024-02", "24年大跌底", "bottom"),
]


def _sse_close(refresh: bool) -> pd.Series:
    """上证综指收盘价（走势叠加用）。"""
    import akshare as ak
    raw = ak.stock_zh_index_daily(symbol="sh000001")
    s = pd.Series(raw["close"].to_numpy(float),
                  index=pd.DatetimeIndex(pd.to_datetime(raw["date"])), name="sse")
    return s.sort_index()


def main(refresh: bool) -> None:
    nt = th.net_temperature("CN", refresh=refresh)
    sse = _sse_close(refresh).reindex(nt.index, method="ffill")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True, height_ratios=[2, 1.4],
        gridspec_kw={"hspace": 0.12},
    )

    # 上：上证综指 + 净温度色带
    ax1.plot(sse.index, sse.values, color="#333", lw=1.0, label="上证综指")
    ax1.set_ylabel("上证综指", fontsize=11)
    ax1.set_title("A股市场温度计 v1 · 历史回看（顶部=过热抓泡沫 / 底部=恐慌抓机会）", fontsize=14)
    axn = ax1.twinx()
    axn.fill_between(nt.index, nt["net"], 0, where=nt["net"] >= 0,
                     color="#d62728", alpha=0.15)
    axn.fill_between(nt.index, nt["net"], 0, where=nt["net"] < 0,
                     color="#2ca02c", alpha=0.15)
    axn.plot(nt.index, nt["net"], color="#888", lw=0.8, label="净温度")
    axn.axhline(40, color="#d62728", ls="--", lw=0.7)
    axn.axhline(-40, color="#2ca02c", ls="--", lw=0.7)
    axn.set_ylabel("净温度 (顶−底)", fontsize=11)
    axn.set_ylim(-110, 110)

    for d, label, side in ANCHORS:
        sub = nt[nt.index <= d]
        if not len(sub):
            continue
        x = sub.index[-1]
        y = sse.reindex([x], method="ffill").iloc[0]
        color = "#d62728" if side == "top" else "#2ca02c"
        ax1.annotate(f"{label}\n净{sub['net'].iloc[-1]:.0f}",
                     xy=(x, y), fontsize=8.5, color=color, ha="center",
                     xytext=(0, 22 if side == "top" else -28),
                     textcoords="offset points",
                     arrowprops=dict(arrowstyle="->", color=color, lw=0.8))

    # 下：顶部 / 底部温度
    ax2.plot(nt.index, nt["top"], color="#d62728", lw=0.9, label="顶部温度(过热)")
    ax2.plot(nt.index, nt["bottom"], color="#2ca02c", lw=0.9, label="底部温度(恐慌)")
    ax2.axhline(75, color="#d62728", ls=":", lw=0.6)
    ax2.axhline(75, color="#2ca02c", ls=":", lw=0.6)
    ax2.set_ylabel("温度 0–100", fontsize=11)
    ax2.set_ylim(0, 100)
    ax2.legend(loc="upper left", fontsize=9, ncol=2)
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    last = nt.iloc[-1]
    fig.text(0.99, 0.01,
             f"截至 {nt.index[-1].date()}：顶部 {last['top']:.0f} / 底部 {last['bottom']:.0f} / 净 {last['net']:+.0f}",
             ha="right", fontsize=9, color="#555")

    out = Path("research/assets/市场温度计_历史回看.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"saved -> {out}  ({nt.index[0].date()} ~ {nt.index[-1].date()}, n={len(nt)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="联网刷新数据")
    main(ap.parse_args().refresh)
