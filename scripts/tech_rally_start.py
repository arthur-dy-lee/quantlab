"""科技板块「从什么时候开始涨」：自然年拆解 + 起涨点定位 + 净值曲线。

回答两个问题：
  1) 涨幅是哪一年贡献的 → 2023 / 2024 / 2025 / 2026今年以来 逐年涨幅 + 各起点累计
  2) 真正的起涨点在哪 → 2023-01-01 以来净值最低点(及日期) + 对数净值曲线

口径同 tech_sector_returns.py：ETF 后复权，指数价格口径。
产出：终端表 + assets/科技板块_起涨点净值曲线.png
"""
from __future__ import annotations
import warnings
from pathlib import Path
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False
ASSETS = Path(__file__).resolve().parents[1] / "research" / "assets"

# theme, kind, code, 是否画进曲线
BASKET = [
    ("半导体设备", "etf",  "159516",  False),  # 2023-07 上市，无2023基数
    ("通信",       "etf",  "515050",  True),
    ("半导体",     "etf",  "512480",  True),
    ("芯片",       "etf",  "159995",  True),
    ("机器人",     "em_i", "931087",  True),
    ("人工智能",   "etf",  "159819",  True),
    ("消费电子",   "etf",  "159732",  False),
    ("科创50",     "sina", "sh000688", True),
    ("AI产业",     "etf",  "512930",  False),
    ("计算机",     "etf",  "512720",  False),
    ("软件",       "etf",  "515230",  False),
    ("云计算",     "etf",  "516510",  False),
    ("沪深300",    "sina", "sh000300", True),
]


def close(kind, code):
    if kind == "etf":
        df = ak.fund_etf_hist_em(symbol=code, period="daily",
                                 start_date="20220101", end_date="20261231", adjust="hfq")
        df = df.rename(columns={"日期": "date", "收盘": "close"})
    elif kind == "em_i":
        df = ak.index_zh_a_hist(symbol=code, period="daily",
                                start_date="20220101", end_date="20261231")
        df = df.rename(columns={"日期": "date", "收盘": "close"})
    else:
        df = ak.stock_zh_index_daily(symbol=code)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()["close"]


def asof(s, d):
    x = s[s.index <= pd.Timestamp(d)]
    return float(x.iloc[-1]) if len(x) else float("nan")


def ret(s, d0, d1):
    a, b = asof(s, d0), asof(s, d1)
    return (b / a - 1) * 100 if a == a and a else float("nan")


series = {}
rows = []
for theme, kind, code, _ in BASKET:
    s = close(kind, code)
    series[theme] = s
    r23 = ret(s, "2022-12-31", "2023-12-31")          # 2023 全年
    r24 = ret(s, "2023-12-31", "2024-12-31")          # 2024 全年
    r25 = ret(s, "2024-12-31", "2025-12-31")          # 2025 全年
    r26 = ret(s, "2025-12-31", "2026-06-30")          # 2026 今年以来
    c23 = ret(s, "2022-12-31", "2026-06-30")          # 自2023初累计
    c24 = ret(s, "2023-12-31", "2026-06-30")          # 自2024初累计
    # 起涨点：2023-01-01 以来净值最低日
    win = s[s.index >= pd.Timestamp("2023-01-01")]
    low_d = win.idxmin()
    rows.append((theme, r23, r24, r25, r26, c24, c23, low_d.date()))

df = pd.DataFrame(rows, columns=["板块", "2023全年", "2024全年", "2025全年",
                                 "2026今年以来", "自2024初累计", "自2023初累计", "起涨低点"])
df = df.sort_values("自2023初累计", ascending=False)
pd.set_option("display.unicode.east_asian_width", True)
fmt = {c: (lambda x: "  —  " if x != x else f"{x:+6.1f}%")
       for c in ["2023全年", "2024全年", "2025全年", "2026今年以来", "自2024初累计", "自2023初累计"]}
print(df.to_string(index=False, formatters=fmt))

# ---- 净值曲线（2023-01-01=1，对数轴）----
fig, ax = plt.subplots(figsize=(13, 7.5))
colors = {"半导体": "#c0392b", "芯片": "#e74c3c", "通信": "#8e44ad", "机器人": "#16a085",
          "人工智能": "#2980b9", "科创50": "#d35400", "沪深300": "#7f8c8d"}
for theme, kind, code, draw in BASKET:
    if not draw:
        continue
    s = series[theme]
    s = s[s.index >= pd.Timestamp("2023-01-01")]
    nav = s / s.iloc[0]
    lw = 2.6 if theme == "沪深300" else 1.8
    ls = "--" if theme == "沪深300" else "-"
    ax.plot(nav.index, nav.values, label=f"{theme} ({nav.iloc[-1]:.1f}x)",
            color=colors.get(theme), lw=lw, ls=ls)

for d, txt, col in [("2024-02-05", "2024-02-05\n微盘股见底", "#444"),
                    ("2024-09-24", "2024-09-24\n「924」政策底", "#c0392b"),
                    ("2025-01-20", "2025-01\nDeepSeek\nAI 催化", "#2980b9")]:
    ax.axvline(pd.Timestamp(d), color=col, lw=1.0, ls=":", alpha=0.8)
    ax.text(pd.Timestamp(d), ax.get_ylim()[0] * 1.02, txt, rotation=0, fontsize=8.5,
            color=col, ha="center", va="bottom")
ax.set_yscale("log")
ax.set_yticks([0.5, 0.7, 1, 1.5, 2, 3, 4, 6, 8])
ax.get_yaxis().set_major_formatter(plt.matplotlib.ticker.ScalarFormatter())
ax.axhline(1.0, color="k", lw=0.7)
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
ax.set_ylabel("净值（2023-01-01 = 1，对数轴）", fontsize=11)
ax.set_title("科技板块起涨点·2023-01-01 至今净值曲线（后复权，对数轴）\n"
             "真正的趋势起点是 2024-09「924」政策底，AI 硬件在 2025 起加速", fontsize=13)
ax.legend(loc="upper left", fontsize=9.5, ncol=2)
ax.grid(alpha=0.25, which="both")
fig.tight_layout()
out = ASSETS / "科技板块_起涨点净值曲线.png"
fig.savefig(out, dpi=140, bbox_inches="tight")
print("\nsaved:", out)
