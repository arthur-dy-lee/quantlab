"""命令行入口（详细设计 §10.2）。"""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from quantlab.bootstrap import build_app
from quantlab.enums import Freq
from quantlab.stats.conditions import Condition, drop_gt, n_down_days, rise_gt, rsi_gt, rsi_lt, vol_spike

app = typer.Typer(add_completion=False, help="QuantLab —— 本地多市场分析/统计概率信号/通知")


def _parse_cond(spec: str) -> Condition:
    """``"drop_gt:0.015,n_down:2"`` → 组合 Condition。"""
    builders = {
        "drop_gt": lambda a: drop_gt(float(a)),
        "rise_gt": lambda a: rise_gt(float(a)),
        "n_down": lambda a: n_down_days(int(a)),
        "rsi_lt": lambda a: rsi_lt(float(a)),
        "rsi_gt": lambda a: rsi_gt(float(a)),
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


def _fmt_prob(r) -> str:
    return (
        f"  样本 N={r.n}  上涨概率 {r.p_up:.1%}  基准率 {r.base_rate:.1%}  edge {r.edge:+.1%}  "
        f"[95%CI {r.ci_low:.1%}~{r.ci_high:.1%}]\n"
        f"  平均 {r.mean_ret:+.2%}  中位 {r.median_ret:+.2%}  盈亏比 {r.payoff:.2f}  "
        f"平均MAE {r.mae:.2%}  可靠? {'是' if r.reliable else '否(样本不足)'}"
    )


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
        typer.echo(f"{m.symbol:<16} {m.freq}  {m.start}~{m.end}  rows={m.rows}  "
                   f"[{m.instrument_type}] src={m.source}")
    typer.echo(f"完成 {len(metas)}/{len(symbols)}")


@app.command(name="download-all")
def download_all(
    market: str = typer.Option("CN", help="CN 全市场 | US 核心科技+ETF | CRYPTO 主流前十"),
    workers: int = typer.Option(0, help="并发数（0=按市场自动；过高易被源限流）"),
    include_etf: bool = typer.Option(False, help="仅 CN：附带 ETF"),
    limit: int = typer.Option(0, help="只下前 N 个（0=全部，用于试跑/测速）"),
    missing_only: bool = typer.Option(False, help="只补本地尚无缓存的标的（用于失败补漏）"),
):
    """批量拉取某市场日线到本地（并发 + 断点续传 + 进度日志）。

    CN=沪深京全量；US=七姐妹+纳指+科技/AI ETF；CRYPTO=主流前十（参考币安市值）。
    """
    from quantlab.enums import Freq
    from quantlab.symbols import Symbol
    from quantlab.universe import (
        download_universe, list_cn_symbols, list_crypto_symbols, list_us_symbols,
    )

    # 每市场：(清单构造, 默认并发)。源越脆弱并发给得越低（kraken 最严，故 3）。
    builders = {
        "CN": (lambda: list_cn_symbols(include_etf=include_etf), 8),
        "US": (list_us_symbols, 6),
        "CRYPTO": (list_crypto_symbols, 3),
    }
    m = market.upper()
    if m not in builders:
        raise typer.BadParameter("market 仅支持 CN | US | CRYPTO")
    build_syms, default_workers = builders[m]
    workers = workers or default_workers

    dm = build_app()
    _setup_run_log(dm.cfg.data_root)
    syms = build_syms()
    if limit:
        syms = syms[:limit]
    if missing_only:
        syms = [s for s in syms if dm.repo.meta(Symbol.parse(s), Freq.DAY) is None]
    typer.echo(f"[{m}] 待下载 {len(syms)} 个标的，并发 {workers}（日志见 {dm.cfg.data_root}watch.log）…")
    res = download_universe(dm, syms, workers=workers, progress_every=200 if m == "CN" else 5)
    typer.echo(f"完成: ok={res['ok']} fail={res['fail']} / {res['total']}")
    if res["failed"]:
        typer.echo(f"失败: {res['failed'][:20]}")


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
    typer.echo(f"{symbol}  条件={r.condition}  forward={r.forward}\n{_fmt_prob(r)}")


@app.command()
def crossmarket(
    lead: str,
    target: str,
    cond: str = typer.Option(..., help='作用在 lead 上, 如 "drop_gt:0.015"'),
    forward: int = 1,
    lag: int = 1,
):
    """跨市场领先预警（如 US:^IXIC → CN:000300）。"""
    from quantlab.stats.crossmarket import crossmarket as cm

    dm = build_app()
    r = cm(dm, lead, target, _parse_cond(cond), forward, lag, dm.cfg.stats_min_samples)
    typer.echo(f"{r.condition}  forward={forward} lag={lag}\n{_fmt_prob(r)}")


@app.command()
def screen(watchlist: str = typer.Option(..., help="config.yaml 中的主题名")):
    """对主题标的池做技术面筛选。"""
    from quantlab.screener.screener import Screener

    dm = build_app()
    syms = [s.key for s in dm.cfg.watchlists.get(watchlist, [])]
    if not syms:
        raise typer.BadParameter(f"watchlist '{watchlist}' 为空或不存在")
    hits = Screener(dm).run(syms)
    for h in hits:
        skip = f"  (跳过 {len(h.skipped)} 条)" if h.skipped else ""
        typer.echo(f"✓ {h.symbol:<16} {', '.join(h.matched)}{skip}")
    typer.echo(f"命中 {len(hits)}/{len(syms)}")


@app.command()
def watch(
    watchlist: str = typer.Option(..., help="config.yaml 中的主题名"),
    channels: list[str] = typer.Option(["console"]),
    forward: int = 1,
):
    """盯盘扫描一轮并推送（cron 触发，跑完即退）。"""
    from quantlab.errors import InsufficientData
    from quantlab.notify.base import NotifyLog, dispatch
    from quantlab.notify.factory import build_notifiers
    from quantlab.signals.scanner import SignalScanner, annotate
    from quantlab.stats.sizing import build_sizer

    dm = build_app()
    cfg = dm.cfg
    _setup_run_log(cfg.data_root)
    log = logging.getLogger("quantlab")

    syms = [s.key for s in cfg.watchlists.get(watchlist, [])]
    if not syms:
        raise typer.BadParameter(f"watchlist '{watchlist}' 为空或不存在")

    signals = SignalScanner(dm).scan(syms)
    notifiers = build_notifiers(cfg)
    nlog = NotifyLog(Path(cfg.data_root) / "quantlab.db")
    sizer = build_sizer(cfg)

    n_sent = 0
    for sig in signals:
        try:
            card = annotate(dm, sig, forward, sizer, cfg.stats_min_samples)
        except InsufficientData:
            continue
        if dispatch(card, channels, notifiers, nlog, cfg.notify.throttle_minutes):
            n_sent += 1
    msg = f"watch[{watchlist}]: 扫描 {len(syms)} 标的, 触发 {len(signals)} 信号, 推送 {n_sent}"
    log.info(msg)
    typer.echo(msg)


@app.command()
def catalog():
    """列出本地数据目录。"""
    metas = build_app().catalog()
    if not metas:
        typer.echo("（本地暂无数据，先 download）")
        return
    for m in metas:
        typer.echo(f"{m.symbol:<16} {m.freq}  {m.start}~{m.end}  rows={m.rows}  "
                   f"[{m.instrument_type}] src={m.source}")


@app.command()
def predict(
    symbol: str,
    horizon: int = 1,
    test_size: float = 0.3,
):
    """ML 预测下一根 K 线涨跌（诚实评估，报相对多数类基准的超额）。"""
    from quantlab.indicators.technical import add_indicators
    from quantlab.ml.predictor import LogisticPredictor, build_dataset

    dm = build_app()
    df = add_indicators(dm.history(symbol))
    X, y = build_dataset(df, horizon)
    rep = LogisticPredictor().evaluate(X, y, test_size)
    typer.echo(
        f"{symbol}  预测 horizon={horizon}\n"
        f"  准确率 {rep['accuracy']:.1%}  多数类基准 {rep['baseline']:.1%}  "
        f"超额 {rep['excess']:+.1%}  测试样本 {rep['n_test']}"
    )


def _setup_run_log(data_root: str) -> None:
    logger = logging.getLogger("quantlab")
    logger.setLevel(logging.INFO)
    path = Path(data_root) / "watch.log"
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        h = logging.FileHandler(path, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(h)


if __name__ == "__main__":
    app()
