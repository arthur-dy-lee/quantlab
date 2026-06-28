#!/usr/bin/env python
"""温度计加减仓顾问：当下读数 + 历史同档证据 + 走查回测。

站在当下回答"该加仓还是减仓"——把市场净温度映射成建议目标仓位%，
并用历史前向收益给当前区间配胜率/期望/下行风险，再因果回测证明规则有效。

输出：终端报告 + research/assets/温度计_加减仓回测.png（净值 vs 买入持有 + 仓位带）。
用法：python scripts/market_position_advisor.py [--refresh] [--horizon 60]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from quantlab.signals import allocator as al

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False


def _report(adv: al.PositionAdvice) -> None:
    print("=" * 66)
    print(f"  A股加减仓顾问 · 截至 {adv.date.date()} · 基准 {adv.index}")
    print("=" * 66)
    print(f"  净温度 {adv.net:+.0f}  (顶部 {adv.top:.0f} / 底部 {adv.bottom:.0f})"
          f"   近 20 日 {adv.momentum:+.1f} → {adv.turning}")
    print(f"  所处区间：{adv.regime}   →   建议目标仓位 {adv.target:.0f}%")
    print("-" * 66)
    print(f"  ▶ {adv.verdict}")
    print("-" * 66)
    if adv.n:
        print(f"  历史同区间「{adv.regime}」未来 {adv.horizon} 日（n={adv.n}）：")
        print(f"    平均 {adv.mean_fwd:+.1%}  中位 {adv.median_fwd:+.1%}  上涨概率 {adv.win_rate:.0%}"
              f"  (Wilson {adv.ci_low:.0%}~{adv.ci_high:.0%})")
        print(f"    平均最大不利波动(MAE) {adv.mae_mean:.1%}   置信度 {adv.confidence}")
    else:
        print(f"  历史同区间「{adv.regime}」样本不足，回退中性仓位。")
    print("=" * 66)


def _backtest_plot(eq, metrics: dict, out: Path) -> None:
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.set_yscale("log")
    ax1.plot(eq.index, eq["strategy"], color="#d62728", lw=1.3, label="温度择仓")
    ax1.plot(eq.index, eq["buy_hold"], color="#888", lw=1.0, ls="--", label="买入持有")
    ax1.set_ylabel("净值（对数，起点=1）", fontsize=11)
    ax1.legend(loc="upper left", fontsize=10)
    ax1.xaxis.set_major_locator(mdates.YearLocator(2))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax2 = ax1.twinx()
    ax2.fill_between(eq.index, eq["position"] * 100, 0, color="#ff7f0e", alpha=0.12)
    ax2.set_ylabel("仓位 %", fontsize=11, color="#ff7f0e")
    ax2.set_ylim(0, 100)

    ax1.set_title("温度计加减仓 · 走查回测（沪深300，因果·信号次日生效）", fontsize=14)
    txt = (f"温度择仓  CAGR {metrics['strat_cagr']:.1%}  最大回撤 {metrics['strat_maxdd']:.0%}"
           f"  夏普 {metrics['strat_sharpe']:.2f}  Calmar {metrics['strat_calmar']:.2f}"
           f"  均仓 {metrics['avg_exposure']:.0%}\n"
           f"买入持有  CAGR {metrics['bh_cagr']:.1%}  最大回撤 {metrics['bh_maxdd']:.0%}"
           f"  夏普 {metrics['bh_sharpe']:.2f}  Calmar {metrics['bh_calmar']:.2f}\n"
           f"诚实提示：不跑赢买入持有，价值在控回撤与纪律；最稳信号是抄极冷底。")
    fig.text(0.99, 0.01, txt, ha="right", fontsize=8.5, color="#555")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"saved -> {out}  ({eq.index[0].date()} ~ {eq.index[-1].date()}, n={len(eq)})")


def main(refresh: bool, horizon: int, index: str | None) -> None:
    adv = al.recommend_position("CN", horizon=horizon, refresh=refresh, index_symbol=index)
    _report(adv)

    eq, metrics = al.backtest_allocation("CN", refresh=False, index_symbol=index)
    print(f"\n  走查回测 {eq.index[0].date()}~{eq.index[-1].date()}："
          f"策略 CAGR {metrics['strat_cagr']:.1%} / 回撤 {metrics['strat_maxdd']:.0%}"
          f"  vs  买入持有 CAGR {metrics['bh_cagr']:.1%} / 回撤 {metrics['bh_maxdd']:.0%}")
    _backtest_plot(eq, metrics, Path("research/assets/温度计_加减仓回测.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="联网刷新温度与指数数据")
    ap.add_argument("--horizon", type=int, default=60, help="前向收益评估期(交易日)")
    ap.add_argument("--index", default=None,
                    help="前向收益基准：沪深300/中证全指/中证500/上证指数 或裸码；缺省读 config")
    args = ap.parse_args()
    main(args.refresh, args.horizon, args.index)
