#!/usr/bin/env python
"""拐点确认清单——判断一个板块/指数的趋势是否在转向（默认科创50）。

**核心原则**：顶预测不了，只能**确认 + 机械止损**。单个信号都是噪声；多个同时转向，
拐点才大概率为真。脚本数信号、给评分和**机械减仓阶梯**，把"该不该走"从情绪里拿出来。

信号（causal，价格/杠杆口径）：跌破 MA20/MA50/MA200、乖离回落、相对大盘转弱、动量转负、两融回落。
**性质**：趋势跟随的退出工具，不是抄顶/预测；melt-up 能透支着继续跑，故"未触发=持有(带止损)"。

用法：python scripts/turning_point.py [--code 000688] [--broad 000985]
"""

from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from quantlab.datasources import valuation_source as vs


def _hist(code: str) -> pd.DataFrame:
    import akshare as ak
    raw = ak.index_zh_a_hist(symbol=code, period="daily",
                             start_date="20160101", end_date=f"{date.today():%Y%m%d}")
    return pd.DataFrame(
        {"close": pd.to_numeric(raw["收盘"], errors="coerce").values},
        index=pd.to_datetime(raw["日期"]),
    ).dropna().sort_index()


def main(code: str, broad_code: str) -> None:
    c = _hist(code)["close"]
    broad = _hist(broad_code)["close"].reindex(c.index).ffill()
    ma20, ma50, ma200 = (c.rolling(w).mean() for w in (20, 50, 200))
    dev = c / ma200 - 1
    rs = c / broad
    try:
        mar = vs.cn_margin_sh().sort_index()
        mar_chg = mar.iloc[-1] / mar.iloc[-21] - 1
    except Exception:  # noqa: BLE001
        mar_chg = float("nan")

    # 每条：(名称, 是否触发拐点信号, 读数)
    sigs = [
        ("跌破 MA20（首道裂缝）", c.iloc[-1] < ma20.iloc[-1], f"{c.iloc[-1] / ma20.iloc[-1] - 1:+.1%}"),
        ("跌破 MA50（趋势走弱）", c.iloc[-1] < ma50.iloc[-1], f"{c.iloc[-1] / ma50.iloc[-1] - 1:+.1%}"),
        ("跌破 MA200（regime 变）", c.iloc[-1] < ma200.iloc[-1], f"{c.iloc[-1] / ma200.iloc[-1] - 1:+.1%}"),
        ("乖离回落（抛物线破）", dev.iloc[-1] < dev.iloc[-21], f"今{dev.iloc[-1]:+.0%}/20日前{dev.iloc[-21]:+.0%}"),
        ("相对大盘转弱（抱团撤）", rs.iloc[-1] < rs.iloc[-21], f"近20日{rs.iloc[-1] / rs.iloc[-21] - 1:+.1%}"),
        ("动量转负（失去动力）", c.iloc[-1] < c.iloc[-21], f"近20日{c.iloc[-1] / c.iloc[-21] - 1:+.1%}"),
        ("两融回落（燃料断）", bool(mar_chg < 0) if mar_chg == mar_chg else False,
         "数据缺" if mar_chg != mar_chg else f"近20日{mar_chg:+.1%}"),
    ]
    score = sum(1 for _, hit, _ in sigs if hit)

    print("=" * 60)
    print(f"  拐点确认清单 · {code} · 截至 {c.index[-1].date()}（收 {c.iloc[-1]:.0f}）")
    print("=" * 60)
    for name, hit, val in sigs:
        print(f"  [{'⚠ 触发' if hit else '— 完好'}] {name:22s} {val}")
    print("-" * 60)
    print(f"  拐点信号 {score}/7 触发")
    if score == 0:
        v = "趋势完好——持有(带止损)，别预测顶；melt-up 能继续跑。"
    elif score <= 2:
        v = "出现裂缝——收紧止损、可先减 1/3，别加仓。"
    elif score <= 4:
        v = "松动明显——拐点大概率在形成，执行减仓(减半起)。"
    else:
        v = "趋势已破——基本确认，清/大幅减。"
    print(f"  研判：{v}")
    print("-" * 60)
    print("  机械减仓阶梯（替你做决定、不靠预测顶）：")
    print("    跌破 MA20 → 减 1/3   ｜   跌破 MA50 或 相对转弱 → 再减 1/3")
    print("    跌破 MA200 → 清剩余   ｜   嫌烦就一根线：跌破 MA50 全走。")
    print("  注：宁可被假信号震出一点、也别在 melt-up 顶上抱满——这类板块顶后常腰斩。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="000688", help="指数代码（默认科创50 000688）")
    ap.add_argument("--broad", default="000985", help="相对强弱基准（默认中证全指）")
    args = ap.parse_args()
    main(args.code, args.broad)
