"""温度计加减仓决策层（v1，A股）。见 research/温度计_加减仓决策_设计.md。

站在当下回答"该加仓还是减仓"——把市场**净温度(状态)** + **温度拐点(动量)** 落到一个
**「建议目标仓位%」(动作)**，并用历史前向收益给当前所处区间配胜率/期望/下行风险。

**方法（回测支撑，让数据说话，而非拍脑袋逆向）**
把历史按「净温度档 × 升/降温」分成区间(cell)，统计每个区间未来 horizon 日的指数收益分布，
取**尾部惩罚的风险调整分** ``score = 均值 + tail_k × 第10分位``（第10分位为负→惩罚下尾），
再把各区间的 score 线性映射(min–max)到仓位 [floor, cap]。于是仓位形状由数据决定：

- **极冷·恐慌底** → 重仓（历史前向收益最高、尾部可控）——真正稳健的边。
- **热(趋势)**   → 中高仓（A股暖区 ~74% 上涨，顺势持有，**不是**机械减仓）。
- **中性死区**   → 轻仓（前向收益期望为负）。
- **极热·泡沫**  → 轻仓（均值虽正但 −20% 级左尾，为控回撤而减，非因均值）。

**诚实边界（务必同步给用户）**：走查回测显示，本叠加层在沪深300(2005–) 上**并不跑赢买入持有**
（风险调整后相当、总收益更低），其价值是**纪律 + 压回撤**（−72%→约 −60%），最稳的信号是抄极冷底。
口径：温度来自全市场中位 PE/PB + ERP + 两融(`thermometer.net_temperature`)；
前向收益打在**沪深300(000300)**——2005 起全历史、最可交易的大盘。
**无未来函数**：温度分位为扩张窗口；回测里区间分数只用已实现样本(s≤t−H)、信号次日生效。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from quantlab.constants import CLOSE
from quantlab.core import forward_return, mae, shift_next_day, wilson_interval
from quantlab.datasources import valuation_source as vs
from quantlab.signals import thermometer as th

# 净温度分档（−100..+100）；±101 让 pd.cut 含端点。
NET_BINS = [-101, -40, -20, 20, 40, 101]
NET_LABELS = ["极冷·机会", "冷", "中性", "热", "极热·泡沫"]

DEFAULT_PARAMS: dict[str, float] = {
    "horizon": 60,         # 前向收益评估期(交易日)
    "mom_window": 20,      # 温度动量窗口(交易日)——区分升温/降温(拐点)
    "tail_k": 1.2,         # 尾部惩罚系数：score = 均值 + tail_k × 第10分位
    "floor": 15.0,         # 仓位下限 %（最差区间也留底仓）
    "cap": 100.0,          # 仓位上限 %
    "min_samples": 40,     # 区间样本下限；不足回退上层档/中性
    "neutral": 50.0,       # 样本不足时的回退仓位 %
    "deadband": 10.0,      # 仓位死区/滞回(个百分点)：目标漂移＜此值不动，降换手不丢绩效
}
DEFAULT_INDEX = "000300"   # 沪深300（2005 起全历史 + 最可交易；中证全指仅 2011 起）

# 可切换的前向收益基准（友好名 → 东财裸 6 位码）。温度本身与指数无关，仅换"收益标尺"。
INDEX_CHOICES: dict[str, str] = {
    "沪深300": "000300",   # 默认：可交易(300ETF/IF)、2005 起含 2008、与 ERP 同口径
    "中证全指": "000985",   # 最贴合全市场中位温度口径(区分度最高)；2011 起、缺 2008
    "中证500": "000905",   # 中小盘视角
    "上证指数": "000001",   # =上证综指(通达信码 1A0001)；编制偏沪市，仅作情绪锚
}
INDEX_NAMES: dict[str, str] = {v: k for k, v in INDEX_CHOICES.items()}


@dataclass
class PositionAdvice:
    """当下的加减仓建议 + 历史同区间前向收益证据。"""
    date: pd.Timestamp
    index: str             # 前向收益基准（友好名，如"沪深300"）
    net: float
    top: float
    bottom: float
    momentum: float        # 净温度近 mom_window 日变化
    turning: str           # 升温 | 降温 | 走平
    band: str              # 净温度档
    regime: str            # 档×拐点（cell）
    target: float          # 建议目标仓位 %
    verdict: str           # 人读结论
    confidence: str        # 高 | 中 | 低
    # —— 历史同区间前向收益证据（同口径打在沪深300）——
    horizon: int
    n: int
    mean_fwd: float        # 未来 horizon 日平均收益
    median_fwd: float
    win_rate: float        # 上涨概率
    ci_low: float          # Wilson 95%
    ci_high: float
    mae_mean: float        # 平均最大不利波动(下行风险)


def _params(config_path: str | None) -> dict[str, float]:
    """读 config.yaml 的 thermometer.cn.advisor，缺失回退默认。"""
    p = dict(DEFAULT_PARAMS)
    if config_path and Path(config_path).exists():
        try:
            import yaml
            cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
            adv = cfg.get("thermometer", {}).get("cn", {}).get("advisor", {}) or {}
            for k in p:
                if k in adv:
                    p[k] = float(adv[k])
        except Exception:  # noqa: BLE001 —— 配置坏了回退默认，不阻断
            pass
    return p


def _index_symbol(config_path: str | None, override: str | None) -> str:
    """解析前向收益基准代码：显式入参 > config.yaml advisor.index_symbol > 默认沪深300。

    入参/配置可写友好名（"中证全指"）或裸码（"000985"），统一归一到裸码。
    """
    raw = override
    if raw is None and config_path and Path(config_path).exists():
        try:
            import yaml
            cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
            raw = cfg.get("thermometer", {}).get("cn", {}).get("advisor", {}).get("index_symbol")
        except Exception:  # noqa: BLE001
            raw = None
    if raw is None:
        return DEFAULT_INDEX
    return INDEX_CHOICES.get(str(raw), str(raw))


# ── 区间标注与打分 ────────────────────────────────────────────────────────

def _labels(net: pd.Series, mom_window: int) -> pd.DataFrame:
    """每个日期的 净温度档 / 升降温 / 区间(cell=档×拐点)。"""
    mom = (net - net.shift(int(mom_window))).rename("momentum")
    band = pd.cut(net, bins=NET_BINS, labels=NET_LABELS).astype("object")
    direction = pd.Series(np.where(mom >= 0, "升温", "降温"), index=net.index)
    direction[mom.isna()] = np.nan
    cell = band.where(band.isna(), band.astype(str) + "·" + direction.astype(str))
    return pd.DataFrame({"momentum": mom, "band": band, "dir": direction, "cell": cell})


def _score(samples: np.ndarray, tail_k: float) -> float:
    """尾部惩罚的风险调整分：均值 + tail_k × 第10分位（左尾越深，分越低）。"""
    return float(samples.mean() + tail_k * np.quantile(samples, 0.10))


def regime_table(net: pd.Series, price: pd.DataFrame, p: dict[str, float]) -> pd.DataFrame:
    """全样本区间表（cell=档×拐点）：n/均值/中位/胜率/Wilson/MAE/score/目标仓位。

    既是给用户看的**证据表**，也是 live 推荐的**仓位来源**。仓位 = score 经 min–max
    线性映射到 [floor, cap]（最优区间→cap、最差→floor），样本<min 的区间用其所属档兜底。
    """
    h = int(p["horizon"])
    lab = _labels(net, p["mom_window"])
    fwd = forward_return(price, h)
    mae_s = mae(price, h)
    df = pd.DataFrame({"net": net, "cell": lab["cell"], "band": lab["band"]}).reindex(price.index).ffill()
    df["fwd"], df["mae"] = fwd, mae_s
    df = df.dropna(subset=["cell", "fwd"])

    def agg(group_col: str) -> pd.DataFrame:
        rows = []
        for key, g in df.groupby(group_col, observed=True):
            n, k = len(g), int((g["fwd"] > 0).sum())
            lo, hi = wilson_interval(k, n)
            rows.append({group_col: str(key), "n": n, "mean": float(g["fwd"].mean()),
                         "median": float(g["fwd"].median()), "win": k / n if n else np.nan,
                         "ci_low": lo, "ci_high": hi, "mae": float(g["mae"].mean()),
                         "score": _score(g["fwd"].to_numpy(), p["tail_k"])})
        return pd.DataFrame(rows)

    cells = agg("cell")
    bands = agg("band").set_index("band")
    ok = cells[cells["n"] >= p["min_samples"]]
    smin, smax = (ok["score"].min(), ok["score"].max()) if len(ok) >= 2 else (0.0, 1.0)

    def to_pos(score: float) -> float:
        if smax <= smin:
            return p["neutral"]
        frac = np.clip((score - smin) / (smax - smin), 0.0, 1.0)
        return float(p["floor"] + (p["cap"] - p["floor"]) * frac)

    cells["band"] = cells["cell"].str.split("·").str[0]
    pos = []
    for _, r in cells.iterrows():
        if r["n"] >= p["min_samples"]:
            pos.append(to_pos(r["score"]))
        elif r["band"] in bands.index and bands.loc[r["band"], "n"] >= p["min_samples"]:
            pos.append(to_pos(float(bands.loc[r["band"], "score"])))
        else:
            pos.append(p["neutral"])
    cells["position"] = pos
    return cells.sort_values("position", ascending=False).reset_index(drop=True)


# ── live 推荐 ─────────────────────────────────────────────────────────────

def _deadband(series: pd.Series, thresh: float) -> pd.Series:
    """滞回：目标值漂移 < thresh 时保持不动，≥thresh 才跳到新目标。滤小抖动、不滞后大 move。

    NaN 透传（持有上一有效值）；thresh 与 series 同量纲。
    """
    held = np.nan
    out = np.empty(len(series))
    for i, v in enumerate(series.to_numpy()):
        if np.isnan(v):
            out[i] = held
            continue
        if np.isnan(held) or abs(v - held) >= thresh:
            held = v
        out[i] = held
    return pd.Series(out, index=series.index, name=series.name)


def _eff_n(n: int, horizon: int) -> float:
    """有效样本量：日频前向收益按 horizon 重叠，独立样本 ≈ n/horizon（自相关打折）。"""
    return max(1.0, n / max(1, horizon))


def _confidence(n: int, win: float, horizon: int) -> str:
    """置信度：用有效样本量(自相关打折) + Wilson 区间是否离开 50%。"""
    eff = _eff_n(n, horizon)
    if not (eff >= 1 and 0 <= win <= 1):
        return "低"
    lo, hi = wilson_interval(int(round(win * eff)), int(round(eff)))
    decisive = (lo > 0.5) or (hi < 0.5)
    if eff >= 8 and decisive:
        return "高"
    if eff >= 4:
        return "中"
    return "低"


def _verdict(target: float, turning: str) -> str:
    if target >= 65:
        stance = f"偏进攻——可持/加仓至约 {target:.0f}%"
    elif target <= 35:
        stance = f"偏防守——宜减仓至约 {target:.0f}%"
    else:
        stance = f"标配——维持约 {target:.0f}%"
    return (f"{stance}（{turning}）。执行：现仓**高于 {target:.0f}% 则减、低于则加**，向目标靠拢。"
            f"注：此为基于历史同区间前向收益的区间仓位，主用于纪律与控回撤，非择时套利。")


def recommend_position(market: str = "CN", horizon: int | None = None, refresh: bool = False,
                       data_root: str = "data/", config_path: str | None = "config.yaml",
                       index_symbol: str | None = None) -> PositionAdvice:
    """当下加减仓建议：当前区间 → 目标仓位% + 同区间历史前向收益证据（全样本口径）。

    ``index_symbol`` 可传友好名("中证全指")或裸码("000985")；None 时读 config / 回退沪深300。
    """
    p = _params(config_path)
    if horizon is not None:
        p["horizon"] = float(horizon)
    sym = _index_symbol(config_path, index_symbol)
    nt = th.net_temperature(market, refresh, data_root, config_path)
    price = vs.cn_index_ohlc(sym, data_root, refresh)
    lab = _labels(nt["net"], p["mom_window"])
    table = regime_table(nt["net"], price, p)

    last = nt.iloc[-1]
    mom = float(lab["momentum"].iloc[-1]) if pd.notna(lab["momentum"].iloc[-1]) else 0.0
    turning = "升温" if mom > 1 else "降温" if mom < -1 else "走平"
    band = str(lab["band"].iloc[-1])
    cell = str(lab["cell"].iloc[-1])

    row = table[table["cell"] == cell]
    if len(row):
        r = row.iloc[0]
        n = int(r["n"])
        mean_fwd, median_fwd, win = float(r["mean"]), float(r["median"]), float(r["win"])
        mae_mean = float(r["mae"])
    else:  # 理论上不该发生（cell 必在表内）
        n = 0
        mean_fwd = median_fwd = win = mae_mean = float("nan")

    # 目标仓位走滞回：把全样本各日的区间仓位连成序列、过死区，取末值＝当下可执行目标
    pos_map = table.set_index("cell")["position"]
    target_series = lab["cell"].map(pos_map).ffill()
    target = float(_deadband(target_series, p["deadband"]).iloc[-1])

    # Wilson 区间按有效样本量(自相关打折)重算，给"诚实"的更宽区间
    if n and pd.notna(win):
        eff = _eff_n(n, int(p["horizon"]))
        ci_low, ci_high = wilson_interval(int(round(win * eff)), int(round(eff)))
    else:
        ci_low = ci_high = float("nan")

    return PositionAdvice(
        date=nt.index[-1], index=INDEX_NAMES.get(sym, sym),
        net=float(last["net"]), top=float(last["top"]),
        bottom=float(last["bottom"]), momentum=mom, turning=turning, band=band, regime=cell,
        target=target, verdict=_verdict(target, turning),
        confidence=_confidence(n, win, int(p["horizon"])), horizon=int(p["horizon"]), n=n,
        mean_fwd=mean_fwd, median_fwd=median_fwd, win_rate=win,
        ci_low=ci_low, ci_high=ci_high, mae_mean=mae_mean,
    )


# ── 走查回测（因果，无未来函数）──────────────────────────────────────────

def causal_positions(net: pd.Series, price: pd.DataFrame, p: dict[str, float]) -> pd.Series:
    """逐日仓位：t 时刻区间分数只用 s≤t−H 的**已实现**前向收益（无未来函数）。

    每个区间按 score=均值+tail_k×p10 打分，对当前已populated区间 min–max → 仓位。
    """
    h = int(p["horizon"])
    lab = _labels(net, p["mom_window"])
    cell = lab["cell"].reindex(price.index).ffill()
    fwd = forward_return(price, h)
    idx = price.index
    store: dict[str, list[float]] = defaultdict(list)
    out = np.full(len(idx), np.nan)
    ptr = 0
    for i in range(len(idx)):
        while ptr <= i - h and ptr < len(idx):        # s 的前向收益于 s+H 已实现
            c, f = cell.iloc[ptr], fwd.iloc[ptr]
            if isinstance(c, str) and pd.notna(f):
                store[c].append(float(f))
            ptr += 1
        c_now = cell.iloc[i]
        if not isinstance(c_now, str):
            continue
        scores = {k: _score(np.asarray(v), p["tail_k"]) for k, v in store.items()
                  if len(v) >= p["min_samples"]}
        if c_now not in store or len(store[c_now]) < p["min_samples"] or len(scores) < 2:
            out[i] = p["neutral"]
            continue
        smin, smax = min(scores.values()), max(scores.values())
        s = scores[c_now]
        frac = 0.5 if smax <= smin else (s - smin) / (smax - smin)
        out[i] = p["floor"] + (p["cap"] - p["floor"]) * np.clip(frac, 0.0, 1.0)
    pos = pd.Series(out, index=idx, name="position")
    if p.get("deadband", 0) > 0:                       # 滞回：滤小抖动、降换手（不滞后大 move）
        pos = _deadband(pos, p["deadband"])
    return pos / 100.0


def _perf(strat: pd.Series, mkt: pd.Series, pos: pd.Series) -> dict[str, float]:
    """策略 vs 买入持有的年化口径绩效（日频，252）。"""
    def cagr(r: pd.Series) -> float:
        eq = float((1 + r).prod())
        yrs = len(r) / 252.0
        return eq ** (1 / yrs) - 1 if yrs > 0 and eq > 0 else float("nan")

    def maxdd(r: pd.Series) -> float:
        eq = (1 + r).cumprod()
        return float((eq / eq.cummax() - 1).min())

    def sharpe(r: pd.Series) -> float:
        sd = r.std()
        return float(r.mean() / sd * np.sqrt(252)) if sd and sd > 0 else float("nan")

    return {
        "strat_cagr": cagr(strat), "bh_cagr": cagr(mkt),
        "strat_maxdd": maxdd(strat), "bh_maxdd": maxdd(mkt),
        "strat_sharpe": sharpe(strat), "bh_sharpe": sharpe(mkt),
        "strat_calmar": cagr(strat) / abs(maxdd(strat)) if maxdd(strat) else float("nan"),
        "bh_calmar": cagr(mkt) / abs(maxdd(mkt)) if maxdd(mkt) else float("nan"),
        "avg_exposure": float(pos.mean()), "turnover": float(pos.diff().abs().sum()),
    }


def backtest_allocation(market: str = "CN", refresh: bool = False, data_root: str = "data/",
                        config_path: str | None = "config.yaml",
                        index_symbol: str | None = None) -> tuple[pd.DataFrame, dict[str, float]]:
    """走查回测：因果地把区间仓位规则铺到历史，对照买入持有。

    返回 (净值表[strategy/buy_hold/position], 绩效 dict)。信号次日生效，自首个有效仓位起算。
    ``index_symbol`` 同 ``recommend_position``。诚实提示：本规则不跑赢买入持有，价值在控回撤。
    """
    p = _params(config_path)
    sym = _index_symbol(config_path, index_symbol)
    nt = th.net_temperature(market, refresh, data_root, config_path)
    price = vs.cn_index_ohlc(sym, data_root, refresh)

    pos = causal_positions(nt["net"], price, p)
    pos = shift_next_day(pos)                          # 信号次日生效（防未来函数）
    started = pos.notna().cummax()
    ret = price[CLOSE].pct_change().fillna(0.0)
    pos = pos.where(started).fillna(0.0)
    strat = (pos * ret)[started]
    ret, pos = ret.loc[strat.index], pos.loc[strat.index]
    out = pd.DataFrame({
        "strategy": (1 + strat).cumprod(),
        "buy_hold": (1 + ret).cumprod(),
        "position": pos,
    })
    return out, _perf(strat, ret, pos)
