#!/usr/bin/env python3
"""上证指数大涨/大跌盘中提醒：当日涨跌幅(相对昨收)超过 ±1.0% 时输出一条提醒。

- 只在 A股交易时段(周一~五 9:30–11:30 / 13:00–15:05)生效，其余时间静默。
- 每个方向(涨/跌)每天只报一次：用 data/index_alert_state.json 去重。
- 命中则向 stdout 打印 "标题\t正文"(供 index_alert.sh 调 pp_push 推送，pp_push 会自动附温度)；
  未命中/非交易时段则不输出。设环境变量 QL_ALERT_FORCE=1 可跳过时段判断(测试用)。
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

STATE = Path("data/index_alert_state.json")
THRESH = 1.0  # 当日涨跌幅阈值(%)


def _trading_now(now: dt.datetime) -> bool:
    if now.weekday() >= 5:                     # 周六/日
        return False
    t = now.time()
    return (dt.time(9, 30) <= t <= dt.time(11, 31)) or (dt.time(13, 0) <= t <= dt.time(15, 5))


def main() -> None:
    now = dt.datetime.now()
    if not os.environ.get("QL_ALERT_FORCE") and not _trading_now(now):
        return

    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        row = df[df["代码"] == "000001"].iloc[0]
        price, chg, prev, pts = (float(row["最新价"]), float(row["涨跌幅"]),
                                 float(row["昨收"]), float(row["涨跌额"]))
    except Exception:  # noqa: BLE001 —— 取数失败就别报，等下次
        return

    if abs(chg) < THRESH:
        return

    direction = "up" if chg > 0 else "down"
    today = now.strftime("%Y-%m-%d")
    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text())
        except Exception:  # noqa: BLE001
            state = {}
    if state.get("date") != today:
        state = {"date": today, "alerted": []}
    if direction in state["alerted"]:          # 今日该方向已报过
        return
    state["alerted"].append(direction)
    STATE.write_text(json.dumps(state, ensure_ascii=False))

    arrow, word = ("📈", "大涨") if chg > 0 else ("📉", "大跌")
    title = f"🚨上证{word} {chg:+.2f}%"
    body = f"{arrow}上证指数 昨收{prev:.0f} → 现价{price:.0f}  {chg:+.2f}% ({pts:+.0f}点)  {now:%H:%M}"
    print(f"{title}\t{body}")


if __name__ == "__main__":
    main()
