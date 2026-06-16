"""盘中定时信号扫描 —— RSI14<25 深超卖反弹 / 强势追涨，触发即推送。

设计：
- 调度：建议盘中每半小时跑一次（见 LaunchAgents plist），只在开市时段触发。
- 交易日守卫：用**新浪实时行情的日期**判断今天是否真在交易（行情日期≠今天 ⇒
  周末/节假日 ⇒ 直接退出）；无需节假日表。
- 数据：新浪日线 + 用实时行情把"今天"这根K线更新为盘中最新，使 RSI 反映实时；
  刷新后置 offline_only，后续只读本地、绝不触发东财。
- 信号/推送：复用 quantlab 的 SignalScanner + notify 链路（默认 console；
  config.yaml 配好飞书/邮件后自动多发）。与回测一致：probability 用 forward=5。

用法（cron/launchd 盘中触发）：python scripts/daily_signal.py
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import akshare as ak
import pandas as pd
import requests

from quantlab.bootstrap import build_app
from quantlab.constants import CLOSE, HIGH, LOW, OPEN, VOLUME
from quantlab.datasources.akshare_source import AkshareSource
from quantlab.enums import Freq, InstrumentType
from quantlab.errors import InsufficientData
from quantlab.notify.base import NotifyLog, dispatch
from quantlab.notify.factory import build_notifiers
from quantlab.signals.scanner import SignalRule, SignalScanner, annotate
from quantlab.stats.conditions import rise_gt, rsi_gt, rsi_lt
from quantlab.stats.sizing import build_sizer
from quantlab.symbols import Symbol

# ---- 可配置项 ----
FORWARD = 5                              # 与回测一致：信号后持有 5 个交易日
CHANNELS = ["console"]                   # 配好飞书后改成 ["console", "feishu"]
THROTTLE_MIN = 120                       # 同一信号 2h 内不重复推送（盘中每半小时扫描，防刷屏）
INDEXES = {"CN:000300": "sh000300"}      # quantlab代码 -> 新浪指数代码（上证待落库后再加）
RULES = [
    SignalRule("深超卖反弹 RSI14<25", "buy", rsi_lt(25)),
    SignalRule("强势追涨 涨>2%&RSI14>75", "buy", rise_gt(0.02) & rsi_gt(75)),
]


def _sina_quote(sina_code: str) -> dict:
    """新浪指数实时行情。字段：0名称 1今开 2昨收 3现价 4最高 5最低 30日期 31时间。"""
    r = requests.get(f"https://hq.sinajs.cn/list={sina_code}", timeout=10,
                     headers={"Referer": "https://finance.sina.com.cn"})
    f = r.text.strip().split('"')[1].split(",")
    return {"open": float(f[1]), "price": float(f[3]), "high": float(f[4]),
            "low": float(f[5]), "date": f[30], "time": f[31]}


def _refresh(dm, ql_code: str, sina_code: str, today: str) -> None:
    """新浪日线落库；并用实时行情把'今天'这根K线更新为盘中最新（RSI 实时化）。"""
    bars = AkshareSource()._normalize(ak.stock_zh_index_daily(symbol=sina_code))
    q = _sina_quote(sina_code)
    if q["date"] == today:                       # 盘中：覆盖/追加今日实时 K 线
        ts = pd.Timestamp(today)
        vol = float(bars.loc[ts, VOLUME]) if (VOLUME in bars.columns and ts in bars.index) else 0.0
        for col, val in ((OPEN, q["open"]), (HIGH, q["high"]),
                         (LOW, q["low"]), (CLOSE, q["price"]), (VOLUME, vol)):
            if col in bars.columns or col in (OPEN, HIGH, LOW, CLOSE, VOLUME):
                bars.loc[ts, col] = val
        bars = bars.sort_index()
    sym = Symbol.parse(ql_code).with_type(InstrumentType.INDEX)
    dm.repo.save(sym, Freq.DAY, bars, source="akshare(sina)")


def main() -> None:
    now = datetime.now()
    dm = build_app()
    cfg = dm.cfg
    logging.basicConfig(
        filename=str(Path(cfg.data_root) / "daily_signal.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("quantlab")

    # 周末：不联网直接退出
    if now.weekday() >= 5:
        print(f"daily_signal: 周末跳过 @ {now:%Y-%m-%d %H:%M}")
        return

    today = now.strftime("%Y-%m-%d")
    # 交易日守卫：实时行情日期 == 今天 才算开市（自动滤掉节假日）
    try:
        probe = _sina_quote(next(iter(INDEXES.values())))
    except Exception as e:  # noqa: BLE001
        log.warning("实时行情获取失败: %s", e)
        print(f"daily_signal: 行情获取失败，跳过 @ {now:%H:%M}")
        return
    if probe["date"] != today:
        msg = f"daily_signal: 非交易日/未开盘（行情日期 {probe['date']}≠{today}），跳过 @ {now:%H:%M}"
        log.info(msg)
        print(msg)
        return

    # 刷新数据（含盘中实时K线）
    for ql, sina in INDEXES.items():
        try:
            _refresh(dm, ql, sina, today)
        except Exception as e:  # noqa: BLE001
            log.warning("刷新失败 %s（用本地缓存继续）: %s", ql, e)
    dm.cfg.offline_only = True  # 之后只读本地

    # 扫描最新一根K线 + 推送
    signals = SignalScanner(dm, RULES).scan(list(INDEXES))
    notifiers = build_notifiers(cfg)
    nlog = NotifyLog(Path(cfg.data_root) / "quantlab.db")
    sizer = build_sizer(cfg)
    n_sent = 0
    for sig in signals:
        try:
            card = annotate(dm, sig, FORWARD, sizer, cfg.stats_min_samples)
        except InsufficientData:
            continue
        if dispatch(card, CHANNELS, notifiers, nlog, THROTTLE_MIN):
            n_sent += 1

    msg = (f"daily_signal: 扫描 {len(INDEXES)} 指数, 触发 {len(signals)} 信号, "
           f"推送 {n_sent}  @ {now:%Y-%m-%d %H:%M}")
    log.info(msg)
    print(msg)


if __name__ == "__main__":
    main()
