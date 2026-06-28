#!/usr/bin/env python
"""板块过热/拥挤监测（价格口径）——抱团有多透支、有没有拐头。

**这不是"估值温度计"**：板块 PE/PB 历史取不到、科创50 才 2020 年没见过完整熊市、
两融占比/证券化率是全市场口径拆不到板块。所以这里走**价格口径**：
乖离 / 回撤 / 相对强弱 / 动量——描述"多透支 + 还在涨还是拐头"。

**性质**：风险**描述**，不是预测择时（动量不可靠预测反转，科创50 能 +39% 乖离还接着涨）。
与广基「温度计·加减仓」配合：温度计看广基该几成仓，本监测看抱团板块本身有多危险。

用法：python scripts/sector_crowding.py [--codes 000688,399006,000985,000300]
"""

from __future__ import annotations

import argparse
from datetime import date

import numpy as np
import pandas as pd

# 友好名 → 指数代码（裸 6 位）。AI/芯片主题指数可自行加代码。
DEFAULT_BOARDS = {
    "科创50": "000688", "创业板指": "399006",
    "中证全指": "000985", "沪深300": "000300",
}
BROAD = "000985"   # 相对强弱的基准（中证全指=广基）


def _close(code: str) -> pd.Series:
    import akshare as ak
    raw = ak.index_zh_a_hist(symbol=code, period="daily",
                             start_date="20100101", end_date=f"{date.today():%Y%m%d}")
    s = pd.Series(pd.to_numeric(raw["收盘"], errors="coerce").values,
                  index=pd.to_datetime(raw["日期"]))
    return s.dropna().sort_index()


def _verdict(dev_pct: float, rs60: float) -> str:
    """透支程度(乖离分位) + 是否还在领涨(相对强弱) → 人读结论。"""
    level = "高度透支" if dev_pct >= 85 else "偏高" if dev_pct >= 60 else "正常"
    trend = "仍领涨·未拐头" if rs60 > 0.02 else "已转弱·留意松动" if rs60 < -0.02 else "走平"
    return f"{level}，{trend}"


def main(codes: dict[str, str]) -> None:
    broad = _close(BROAD)
    print("=" * 78)
    print(f"  板块拥挤监测（价格口径，非估值温度）· {date.today()}")
    print("=" * 78)
    print(f"  {'板块':8s}{'MA200乖离':>10s}{'乖离分位':>9s}{'距1年高':>8s}"
          f"{'近60日':>8s}{'相对全指60日':>13s}  研判")
    print("-" * 78)
    for nm, c in codes.items():
        s = _close(c)
        if s is None or len(s) < 260:
            print(f"  {nm:8s}  数据不足（{c}）")
            continue
        ma = s.rolling(200).mean()
        dev = s.iloc[-1] / ma.iloc[-1] - 1
        dev_hist = (s / ma - 1).dropna()
        dev_pct = float((dev_hist <= dev_hist.iloc[-1]).mean() * 100)
        dd = s.iloc[-1] / s.rolling(250).max().iloc[-1] - 1
        mom = s.iloc[-1] / s.iloc[-60] - 1
        rs = s / broad.reindex(s.index).ffill()
        rs60 = rs.iloc[-1] / rs.iloc[-60] - 1
        print(f"  {nm:8s}{dev:>+10.0%}{dev_pct:>8.0f}{dd:>+8.0%}{mom:>+8.0%}"
              f"{rs60:>+13.0%}  {_verdict(dev_pct, rs60)}")
    print("-" * 78)
    print("  乖离=离200日均线多远(越高越透支)；乖离分位=该乖离在自身历史的位置；")
    print("  距1年高=离近250日高点的回撤；相对全指60日=近60日跑赢/输中证全指(正=还在领涨)。")
    print("  抱团松动的信号：相对强弱转负 + 乖离回落。当前未出现则抱团仍在(可透支但别盲目空)。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default=None,
                    help="逗号分隔的指数代码；缺省=科创50/创业板/中证全指/沪深300")
    args = ap.parse_args()
    boards = DEFAULT_BOARDS if not args.codes else {
        c: c for c in args.codes.split(",")}
    main(boards)
