#!/usr/bin/env python3
"""输出一行「当前 A股市场温度」，供推送消息附带。失败则输出空串(不影响推送)。

净温度 = 顶部(过热) − 底部(恐慌)，范围 −100..100：>+40 偏泡沫，<−40 偏机会。
用缓存(refresh=False)，数据由每周六的 gdp 任务刷新。
"""
from __future__ import annotations


def main() -> None:
    try:
        from quantlab.signals.thermometer import net_temperature
        df = net_temperature("CN")
        r = df.iloc[-1]
        net, top, bot = float(r["net"]), float(r["top"]), float(r["bottom"])
        when = df.index[-1].date()
        if net > 40:
            lab = "🔴过热(偏泡沫)"
        elif net > 15:
            lab = "🟠偏热"
        elif net < -40:
            lab = "🟢机会(偏恐慌)"
        elif net < -15:
            lab = "🔵偏冷"
        else:
            lab = "⚪中性"
        print(f"🌡️A股温度 净{net:+.0f} (顶{top:.0f}/底{bot:.0f}) {lab} @{when}")
    except Exception:  # noqa: BLE001 —— 温度算不出就不附带，绝不阻断推送
        print("")


if __name__ == "__main__":
    main()
