"""命令行入口（详细设计 §10.2）。"""

from __future__ import annotations

import typer

from quantlab.bootstrap import build_app
from quantlab.enums import Freq
from quantlab.stats.conditions import Condition, drop_gt, n_down_days, rsi_lt, vol_spike

app = typer.Typer(add_completion=False, help="QuantLab —— 本地多市场分析/统计概率信号/通知")


def _parse_cond(spec: str) -> Condition:
    """``"drop_gt:0.015,n_down:2"`` → 组合 Condition。"""
    builders = {
        "drop_gt": lambda a: drop_gt(float(a)),
        "n_down": lambda a: n_down_days(int(a)),
        "rsi_lt": lambda a: rsi_lt(float(a)),
        "vol_spike": lambda a: vol_spike(float(a) if a else 2.0),
    }
    conds = []
    for part in spec.split(","):
        name, _, arg = part.strip().partition(":")
        if name not in builders:
            raise typer.BadParameter(f"未知条件 {name}（可用: {list(builders)}）")
        conds.append(builders[name](arg))
    c = conds[0]
    for x in conds[1:]:
        c = c & x
    return c


@app.command()
def download(
    symbols: list[str] = typer.Argument(..., help="如 US:AAPL CN:600519"),
    start: str = typer.Option(None),
    end: str = typer.Option(None),
    freq: str = typer.Option("1d"),
):
    """批量下载并缓存历史。"""
    dm = build_app()
    metas = dm.download(symbols, start, end, Freq(freq))
    for m in metas:
        typer.echo(f"{m.symbol:<14} {m.freq}  {m.start}~{m.end}  rows={m.rows}  "
                   f"[{m.instrument_type}] src={m.source}")
    typer.echo(f"完成 {len(metas)}/{len(symbols)}")


@app.command()
def quote(symbol: str):
    """在线（延迟）行情快照。"""
    q = build_app().quote(symbol)
    chg = f"{q.change_pct:+.2%}" if q.change_pct is not None else "—"
    typer.echo(f"{symbol}  {q.price}  {chg}  @ {q.time:%Y-%m-%d %H:%M}  {q.note}")


@app.command()
def backtest(
    symbol: str,
    strategy: str = typer.Option("dualma", help="dualma | rsi"),
    fast: int = 5,
    slow: int = 20,
    cost_bps: float = 5.0,
):
    """单标的回测。"""
    from quantlab.backtest.engine import Backtester
    from quantlab.backtest.strategies import DualMAStrategy, RsiReversionStrategy

    df = build_app().history(symbol)
    strat = RsiReversionStrategy() if strategy == "rsi" else DualMAStrategy(fast, slow)
    r = Backtester(cost_bps).run(df, strat)
    typer.echo(
        f"{symbol}  策略={strategy}\n"
        f"  总收益 {r.total_return:+.1%}  CAGR {r.cagr:+.1%}  夏普 {r.sharpe:.2f}  "
        f"最大回撤 {r.max_drawdown:.1%}  交易 {r.n_trades} 次\n"
        f"  买入持有对照 总收益 {r.buy_hold.iloc[-1] - 1:+.1%}"
    )


@app.command()
def stats(
    symbol: str,
    cond: str = typer.Option(..., help='如 "drop_gt:0.015,n_down:2"'),
    forward: int = 1,
):
    """条件概率统计（含 base_rate / edge / CI）。"""
    from quantlab.indicators.technical import add_indicators
    from quantlab.stats.probability import probability

    dm = build_app()
    df = add_indicators(dm.history(symbol))
    r = probability(df, _parse_cond(cond), forward, dm.cfg.stats_min_samples, symbol)
    typer.echo(
        f"{symbol}  条件={r.condition}  forward={r.forward}\n"
        f"  样本 N={r.n}  上涨概率 {r.p_up:.1%}  基准率 {r.base_rate:.1%}  edge {r.edge:+.1%}  "
        f"[95%CI {r.ci_low:.1%}~{r.ci_high:.1%}]\n"
        f"  平均 {r.mean_ret:+.2%}  中位 {r.median_ret:+.2%}  盈亏比 {r.payoff:.2f}  "
        f"平均MAE {r.mae:.2%}  可靠? {'是' if r.reliable else '否(样本不足)'}"
    )


@app.command()
def catalog():
    """列出本地数据目录。"""
    metas = build_app().catalog()
    if not metas:
        typer.echo("（本地暂无数据，先 download）")
        return
    for m in metas:
        typer.echo(f"{m.symbol:<14} {m.freq}  {m.start}~{m.end}  rows={m.rows}  "
                   f"[{m.instrument_type}] src={m.source}")


@app.command()
def watch(
    watchlist: str = typer.Option(..., help="config.yaml 中的主题名"),
    channels: list[str] = typer.Option(["console"]),
):
    """盯盘扫描一轮并推送（cron 触发，跑完即退）。M2。"""
    raise NotImplementedError("TODO(M2): watch")


if __name__ == "__main__":
    app()
