"""白银择时：金银比(GSR) + 银价分位 —— 「银见底→银股才有左侧」。

逻辑：白银是黄金的高 β。历史大底常伴随 **GSR 冲高(银相对金极便宜)** + **银价自身分位回落到低位**。
两者同时满足≈银见底信号；银股(盛达/兴业等)是银的高 β，左侧应在该信号触发后(或同步)出现。

产出：research/assets/白银_金银比_银价分位择时.png
用法：python scripts/silver_gsr_timing.py
"""
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import yfinance as yf

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False

ASSETS = Path("/Users/arthur.lee/codes/quantlab/research/assets")
RED, GREEN, BLUE, GREY = "#c0392b", "#1e8449", "#2471a3", "#7f8c8d"


def closes(t):
    d = yf.download(t, period="max", interval="1d", auto_adjust=False, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d["Close"].dropna()


ag, au = closes("SI=F"), closes("GC=F")
m = pd.concat([au.rename("au"), ag.rename("ag")], axis=1).dropna()
m = m[m.index >= "2004-01-01"]
m["gsr"] = m["au"] / m["ag"]
gsr = m["gsr"]
silver = m["ag"]
now = m.index[-1]
cur_gsr = float(gsr.iloc[-1])
cur_ag = float(silver.iloc[-1])

# 分位
ag_pct_all = float((silver < cur_ag).mean() * 100)
ag5 = silver[silver.index >= now - pd.Timedelta(days=365 * 5)]
ag_pct_5y = float((ag5 < cur_ag).mean() * 100)
gsr_pct = float((gsr < cur_gsr).mean() * 100)

# 银价分位序列（扩张窗口，无未来函数），用于下面板叠加
ag_rank = silver.expanding(min_periods=250).apply(lambda x: (x < x.iloc[-1]).mean() * 100, raw=False)

# 历史银大底（GSR 高位）& 银顶（GSR 低位）锚点
ANCHORS = [
    ("2008-10-27", "08熊·银底\nGSR~84", "bottom"),
    ("2011-04-25", "11银顶\nGSR~32", "top"),
    ("2020-03-18", "20疫情·银底\nGSR~124", "bottom"),
    ("2026-01-29", "26银顶\nGSR~44", "top"),
]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                               gridspec_kw={"hspace": 0.12, "height_ratios": [1, 1.05]})

# ---- 上：银价(对数) ----
ax1.semilogy(silver.index, silver.values, color="#34495e", lw=1.1)
ax1.scatter([now], [cur_ag], color=RED, zorder=6, s=55)
ax1.annotate(f"现 ${cur_ag:.0f}\n全历史{ag_pct_all:.0f}分位·5年{ag_pct_5y:.0f}分位",
             (now, cur_ag), xytext=(-95, -38), textcoords="offset points",
             color=RED, fontsize=10, fontweight="bold")
ax1.set_ylabel("COMEX 银 $/oz（对数）", fontsize=11)
ax1.set_title("图6｜白银择时：金银比(GSR) + 银价分位——「银见底」信号未触发，银股左侧未到", fontsize=13)
ax1.grid(alpha=0.25, which="both")

# ---- 下：金银比 + 区带 ----
ax2.axhspan(85, gsr.max() * 1.02, color=GREEN, alpha=0.10)
ax2.axhspan(gsr.min() * 0.98, 50, color=RED, alpha=0.08)
ax2.plot(gsr.index, gsr.values, color="#8e44ad", lw=1.2, label="金银比 GSR")
ax2.axhline(85, color=GREEN, lw=1.0, ls="--")
ax2.axhline(50, color=RED, lw=1.0, ls="--")
ax2.text(pd.Timestamp("2012-09-01"), 112, "GSR≥85：银相对金极便宜 → 历史大底常在此区",
         color=GREEN, fontsize=9.5, va="center")
ax2.text(pd.Timestamp("2014-06-01"), 43, "GSR≤50：银相对金贵 → 银见顶区",
         color=RED, fontsize=9.5, va="center")
ax2.scatter([now], [cur_gsr], color=RED, zorder=6, s=55)
ax2.annotate(f"现 GSR {cur_gsr:.0f}（{gsr_pct:.0f}分位·中性）\n从1月极端低位44(银太贵)修复中",
             (now, cur_gsr), xytext=(-205, 14), textcoords="offset points",
             color=RED, fontsize=10, fontweight="bold")
for d, label, kind in ANCHORS:
    ts = pd.Timestamp(d)
    if ts < gsr.index[0] or ts > gsr.index[-1]:
        continue
    yv = float(gsr.loc[:ts].iloc[-1])
    col = GREEN if kind == "bottom" else RED
    ax2.scatter([ts], [yv], color=col, s=40, zorder=5, marker="^" if kind == "bottom" else "v")
    ax2.annotate(label, (ts, yv), xytext=(0, 10 if kind == "bottom" else -28),
                 textcoords="offset points", color=col, fontsize=8.5, ha="center")
ax2.set_ylabel("金银比 GSR（金价/银价）", fontsize=11)
ax2.grid(alpha=0.25)
ax2.legend(loc="upper left", fontsize=9)
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

# 当前读数文本框
txt = (f"当前读数：GSR {cur_gsr:.0f}（中性，未到≥85 的银见底区）｜"
       f"银价全历史 {ag_pct_all:.0f}分位、5年 {ag_pct_5y:.0f}分位（仍偏高，未到低位）\n"
       f"→ 银见底两条件（GSR≥85 且 银价分位回落到低位）一条都没满足；"
       f"银股是银的高β，左侧应在信号触发后，现仍属下跌中继。")
fig.text(0.5, 0.015, txt, ha="center", fontsize=10.5, color="#34495e",
         bbox=dict(boxstyle="round", fc="#fdf6e3", ec=GREY))

fig.savefig(ASSETS / "白银_金银比_银价分位择时.png", dpi=130, bbox_inches="tight")
plt.close(fig)
print(f"GSR={cur_gsr:.1f}(分位{gsr_pct:.0f}%)  银价${cur_ag:.1f}(全历史{ag_pct_all:.0f}%·5年{ag_pct_5y:.0f}%)")
print("已输出 research/assets/白银_金银比_银价分位择时.png")
