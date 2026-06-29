"""高科技板块三窗口涨幅对比（科创50 / 芯片 / AI / 机器人 + 信创/设备/消费电子/军工/医疗/港股科技 …）。

口径：ETF 用**后复权**(含分红再投)；指数(科创50/沪深300/中证机器人)为价格口径。
三窗口均以**上一年末收盘价**为基准：
  ① 今年以来    : 2025-12-31 收盘 → 最新
  ② 2025.1.1至今: 2024-12-31 收盘 → 最新
  ③ 2025 全年   : 2024-12-31 收盘 → 2025-12-31 收盘
另算 ETF 后复权 vs 不复权 的口径差(②窗口)，量化口径敏感性。

产出：终端表 + assets/科技板块_三窗口涨幅.png + scratchpad/tech_sector_returns.json
"""
from __future__ import annotations
import json, warnings
from pathlib import Path
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False

ASSETS = Path(__file__).resolve().parents[1] / "research" / "assets"
SCRATCH = Path("/private/tmp/claude-501/-Users-arthur-lee-codes-quantlab-research/"
               "fe733c3f-d936-448e-9d21-939cc36f67a5/scratchpad")

# group, theme, kind(etf/sina/em_i), code, label
BASKET = [
    ("算力硬件", "科创50",   "sina", "sh000688", "科创50指数"),
    ("算力硬件", "半导体",   "etf",  "512480",   "半导体ETF(国联安)"),
    ("算力硬件", "芯片",     "etf",  "159995",   "芯片ETF(华夏)"),
    ("算力硬件", "半导体设备","etf", "159516",   "半导体设备ETF(国泰)"),
    ("算力硬件", "通信",     "etf",  "515050",   "通信ETF(华夏·含光模块)"),
    ("算力硬件", "消费电子", "etf",  "159732",   "消费电子ETF(华夏)"),
    ("AI软件",  "人工智能", "etf",  "159819",   "人工智能ETF(易方达)"),
    ("AI软件",  "AI产业",   "etf",  "512930",   "AI人工智能ETF(平安)"),
    ("AI软件",  "计算机",   "etf",  "512720",   "计算机ETF(国泰)"),
    ("AI软件",  "软件",     "etf",  "515230",   "软件ETF(国泰)"),
    ("AI软件",  "云计算",   "etf",  "516510",   "云计算ETF(易方达)"),
    ("AI软件",  "信创",     "etf",  "562030",   "信创ETF(华宝)"),
    ("智能制造","机器人",   "em_i", "931087",   "中证机器人指数"),
    ("智能制造","新能源车", "etf",  "515030",   "新能源车ETF(华夏)"),
    ("智能制造","光伏",     "etf",  "515790",   "光伏ETF(华泰柏瑞)"),
    ("智能制造","军工",     "etf",  "512660",   "军工ETF(国泰)"),
    ("医药",    "创新药",   "etf",  "159992",   "创新药ETF(银华)"),
    ("医药",    "医疗器械", "etf",  "159883",   "医疗器械ETF(永赢)"),
    ("港股科技","恒生科技", "etf",  "513180",   "恒生科技ETF(华夏)"),
    ("港股科技","中概互联", "etf",  "513050",   "中概互联网ETF(易方达·≈KWEB)"),
    ("基准",    "沪深300",  "sina", "sh000300", "沪深300(基准)"),
]


def close(kind, code, adjust="hfq"):
    if kind == "etf":
        df = ak.fund_etf_hist_em(symbol=code, period="daily",
                                 start_date="20180101", end_date="20261231", adjust=adjust)
        df = df.rename(columns={"日期": "date", "收盘": "close"})
    elif kind == "em_i":
        df = ak.index_zh_a_hist(symbol=code, period="daily",
                                start_date="20180101", end_date="20261231")
        df = df.rename(columns={"日期": "date", "收盘": "close"})
    else:
        df = ak.stock_zh_index_daily(symbol=code)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()["close"]


def asof(s, d):
    x = s[s.index <= pd.Timestamp(d)]
    return (x.index[-1], float(x.iloc[-1])) if len(x) else (None, None)


rows = []
for group, theme, kind, code, label in BASKET:
    s = close(kind, code)
    _, b25 = asof(s, "2024-12-31")
    _, b26 = asof(s, "2025-12-31")
    d_last, last = asof(s, "2026-06-30")
    _, e25 = asof(s, "2025-12-31")
    rec = dict(group=group, theme=theme, label=label, kind=kind, code=code,
               ytd2026=last / b26 - 1, since2025=last / b25 - 1, full2025=e25 / b25 - 1,
               asof=str(d_last.date()))
    # 口径差：ETF 后复权 vs 不复权（②窗口）
    if kind == "etf":
        sr = close(kind, code, adjust="")
        _, rb25 = asof(sr, "2024-12-31")
        _, rl = asof(sr, "2026-06-30")
        rec["since2025_raw"] = rl / rb25 - 1
        rec["caliber_gap"] = rec["since2025"] - rec["since2025_raw"]
    rows.append(rec)

df = pd.DataFrame(rows).sort_values("since2025", ascending=False).reset_index(drop=True)

# ---- 终端表 ----
pd.set_option("display.unicode.east_asian_width", True)
show = df[["theme", "label", "ytd2026", "since2025", "full2025"]].copy()
for c in ["ytd2026", "since2025", "full2025"]:
    show[c] = (show[c] * 100).map(lambda x: f"{x:+6.1f}%")
print(show.to_string(index=False))
# 口径差≠分红：缺口大者皆因份额折算(拆分)，不复权有断点须弃用，后复权已对跟踪指数验证
split = df[df["caliber_gap"].abs() > 0.15].sort_values("caliber_gap", ascending=False)
print("\n份额折算导致不复权失真的标的(|gap|>15pp，须用后复权)：")
for _, r in split.iterrows():
    print(f"  {r['code']} {r['theme']:6s} 后复权{r['since2025']*100:+6.1f}%  "
          f"不复权{r['since2025_raw']*100:+6.1f}%  差{r['caliber_gap']*100:+6.1f}pp")
print(f"其余 {len(df.dropna(subset=['caliber_gap']))-len(split)} 只 ETF 后复权≈不复权(无分红/折算，差≈0)")
print("asof:", df["asof"].min(), "~", df["asof"].max())

# ---- 落盘 ----
SCRATCH.mkdir(parents=True, exist_ok=True)
df.to_json(SCRATCH / "tech_sector_returns.json", orient="records", force_ascii=False, indent=2)

# ---- 柱状图（横向分组，按②累计排序）----
plot = df[df["theme"] != "沪深300"].iloc[::-1].reset_index(drop=True)  # 反转使最高在顶
hs = df[df["theme"] == "沪深300"].iloc[0]
y = range(len(plot)); h = 0.26
fig, ax = plt.subplots(figsize=(11.5, 13))
ax.barh([i + h for i in y], plot["since2025"] * 100, h, label="② 2025.1.1 至今(累计)", color="#c0392b")
ax.barh([i for i in y],     plot["full2025"] * 100, h, label="③ 2025 全年",          color="#e08e0b")
ax.barh([i - h for i in y], plot["ytd2026"] * 100,  h, label="① 2026 今年以来",        color="#2e86c1")
for i in y:
    for off, col in [("since2025", "#c0392b"), ("full2025", "#e08e0b"), ("ytd2026", "#2e86c1")]:
        v = plot.loc[i, off] * 100
        dy = {"since2025": h, "full2025": 0, "ytd2026": -h}[off]
        ax.text(v + (3 if v >= 0 else -3), i + dy, f"{v:+.0f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=7.5, color=col)
ax.set_yticks(list(y)); ax.set_yticklabels(plot["theme"], fontsize=10)
ax.axvline(0, color="k", lw=0.8)
for hv, st in [(hs["since2025"]*100, "-"), (hs["ytd2026"]*100, ":")]:
    ax.axvline(hv, color="#7f8c8d", lw=1.0, ls=st)
ax.text(hs["since2025"]*100, len(plot)-0.3, f"沪深300 累计{hs['since2025']*100:+.0f}",
        color="#7f8c8d", fontsize=8.5, ha="center")
ax.set_xlabel("涨幅 %", fontsize=11)
ax.set_title("A股高科技板块·三窗口涨幅对比（后复权，按2025年初至今累计排序）\n"
             f"截至 {df['asof'].max()}；ETF含分红再投，指数为价格口径", fontsize=13)
ax.legend(loc="lower right", fontsize=10, framealpha=0.9)
ax.grid(axis="x", alpha=0.25)
fig.tight_layout()
out = ASSETS / "科技板块_三窗口涨幅.png"
fig.savefig(out, dpi=140, bbox_inches="tight")
print("saved:", out)
