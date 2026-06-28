#!/usr/bin/env python
"""因子 IC 诊断：每个温度计因子对各指数未来收益的预测力 + 共线性 + IC 权重 vs 手设 + 走查对照。

结论(实测)：IC 加权≈手设(走查 Calmar/夏普 差异在噪声级)，**不替换默认手设权重**；
本报告作为"哪个因子真在预测、权重是否合理"的诊断视角。详见 research/温度计_加减仓决策_设计.md §7。

用法：python scripts/factor_ic_report.py [--horizon 60]
"""

from __future__ import annotations

import argparse

import pandas as pd

from quantlab.core import forward_return, shift_next_day
from quantlab.signals import allocator as al, factor_weights as fw, thermometer as th
from quantlab.datasources import valuation_source as vs

INDICES = {"中证全指": "000985", "沪深300": "000300", "中证500": "000905"}


def main(horizon: int) -> None:
    hot = fw.factor_hot_scores()
    p = al._params("config.yaml")

    print("=" * 70)
    print("  ① 单因子前向 IC（hot分位 vs 未来收益；负=方向对、|值|越大越强）")
    print("=" * 70)
    for nm, code in INDICES.items():
        px = vs.cn_index_ohlc(code)
        line = []
        for h in (20, horizon, 120):
            fwd = forward_return(px, h)
            d = hot.reindex(px.index).ffill().assign(fwd=fwd).dropna()
            ics = {k: fw._rank_ic(d[k], d["fwd"]) for k in fw.FACTORS}
            line.append(f"  {h:3d}日: " + " ".join(f"{k} {ics[k]:+.2f}" for k in fw.FACTORS))
        print(f"[{nm}]\n" + "\n".join(line))

    print("\n" + "=" * 70)
    print("  ② 因子共线性（hot分位秩相关；PE/PB≈0.9 即近同一因子→合并）")
    print("=" * 70)
    print(hot.rank().corr().round(2).to_string())

    print("\n" + "=" * 70)
    print(f"  ③ IC 权重(全样本, {horizon}日) vs 现行手设")
    print("=" * 70)
    cur_top, cur_bot = th.DEFAULT_WEIGHTS[("CN", "top")], th.DEFAULT_WEIGHTS[("CN", "bottom")]
    for nm, code in INDICES.items():
        _, w = fw.ic_net_live(code, horizon=horizon)
        print(f"[{nm}] IC: " + "  ".join(f"{k} {w[k]:.0%}" for k in fw.FACTORS))
    print("现行手设 top   : " + "  ".join(f"{k} {cur_top.get(k, 0):.0%}" for k in fw.FACTORS))
    print("现行手设 bottom: " + "  ".join(f"{k} {cur_bot.get(k, 0):.0%}" for k in fw.FACTORS))

    print("\n" + "=" * 70)
    print(f"  ④ 走查对照：IC 加权 vs 手设净温度（因果回测，{horizon}日评估）")
    print("=" * 70)
    hand = th.net_temperature("CN")["net"]
    print(f"{'指数':8s}{'权重':6s}{'区分度':>8s}{'Calmar':>8s}{'夏普':>6s}")

    def bt(net: pd.Series, code: str):
        px = vs.cn_index_ohlc(code)
        t = al.regime_table(net, px, p)
        span = (t[t["n"] >= p["min_samples"]]["win"].agg(lambda s: s.max() - s.min()))
        pos = shift_next_day(al.causal_positions(net, px, p))
        started = pos.notna().cummax()
        ret = px["close"].pct_change().fillna(0.0)
        pos = pos.where(started).fillna(0.0)
        strat = (pos * ret)[started]
        m = al._perf(strat, ret.loc[strat.index], pos.loc[strat.index].fillna(0.0))
        return span, m["strat_calmar"], m["strat_sharpe"]

    for nm, code in INDICES.items():
        h = bt(hand, code)
        ic = bt(fw.ic_net_causal(code, horizon=horizon), code)
        print(f"{nm:7s}{'手设':5s}{h[0]:>8.0%}{h[1]:>8.2f}{h[2]:>6.2f}")
        print(f"{'':7s}{'IC':5s}{ic[0]:>8.0%}{ic[1]:>8.2f}{ic[2]:>6.2f}")
    print("\n结论：IC≈手设(噪声级)，不替换默认；IC 仅作因子诊断视角。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=60, help="前向收益评估期(交易日)")
    main(ap.parse_args().horizon)
