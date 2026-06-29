#!/usr/bin/env python3
"""输出「当前 A股市场温度 + 各因子分位」多行文本，供推送消息附带。

- 净温度 = 顶部(过热) − 底部(恐慌)，−100..100：>+40 偏泡沫，<−40 偏机会。
- 因子分位：PE/PB/ERP/情绪(两融占比) 的历史「热度」分位(0–100，越高越贵/越热)。
- 证券化率(巴菲特指数)：当前值 + 历史分位，独立估值锚。
用缓存(refresh=False)，数据由每周六 gdp 任务刷新；任何异常输出空串，绝不阻断推送。
"""
from __future__ import annotations


def _label(net: float) -> str:
    if net > 40:
        return "🔴过热(偏泡沫)"
    if net > 15:
        return "🟠偏热"
    if net < -40:
        return "🟢机会(偏恐慌)"
    if net < -15:
        return "🔵偏冷"
    return "⚪中性"


def main() -> None:
    try:
        from quantlab.signals.thermometer import compute_temperature
        top = compute_temperature("CN", "top")      # 含 pct_pe/pct_pb/pct_erp/pct_sentiment + temperature(=顶部)
        bot = compute_temperature("CN", "bottom")["temperature"]
        t = top.iloc[-1]
        topv = float(t["temperature"])
        botv = float(bot.reindex(top.index).iloc[-1])
        net = topv - botv
        when = top.index[-1].date()

        def g(k: str) -> str:
            v = t.get(f"pct_{k}")
            return f"{float(v):.0f}" if v == v else "—"   # NaN→—

        lines = [
            f"🌡️A股温度 净{net:+.0f} (顶{topv:.0f}/底{botv:.0f}) {_label(net)}",
            f"📊因子分位↑越热 PE{g('pe')} PB{g('pb')} ERP{g('erp')} 情绪{g('sentiment')}",
        ]

        # 证券化率(巴菲特指数)——独立估值因子
        try:
            from quantlab.datasources.macro_source import china_securitization, historical_percentile
            cn = china_securitization()
            ratio = cn["ratio"].dropna()
            pc = float(historical_percentile(ratio).iloc[-1])
            lines.append(f"💰证券化率 {float(ratio.iloc[-1]):.0f}% (历史{pc:.0f}分位)")
        except Exception:  # noqa: BLE001
            pass

        lines.append(f"@{when}")
        print("\n".join(lines))
    except Exception:  # noqa: BLE001
        print("")


if __name__ == "__main__":
    main()
