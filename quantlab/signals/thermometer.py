"""市场温度计合成（v1，A股）。详见 research/市场温度计_v1详细设计.md。

把 4 个指标各自转成「历史分位(0–100)」，按方向对齐到「顶部温度/底部温度」，
再按权重加权（缺数据按剩余权重归一化），输出 0–100 的温度分。

- 顶部温度（过热）：值越高 = 越接近泡沫顶。
- 底部温度（恐慌）：值越高 = 越接近机会底。
- 净温度 = 顶部 − 底部（−100..100），>+40 偏泡沫、<−40 偏机会。

指标方向（DIRECTION）：
- "high"：原值越高越贵/越热（PE、PB、两融占比）。
- "low" ：原值越低越贵/越热（ERP，盈利收益率减国债，越低股票越贵）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from quantlab.datasources import valuation_source as vs
from quantlab.datasources.macro_source import historical_percentile

# securitization=证券化率(总市值/GDP,巴菲特指标)，高=贵；实测对沪深300前向 IC 最强(−0.52)。
DIRECTION = {"pe": "high", "pb": "high", "erp": "low", "sentiment": "high",
             "securitization": "high"}

# v1.1 默认权重（5 因子；加入证券化率、回收两融的过度权重）。config.yaml 可覆盖。
# 顶部=过热(抓泡沫)：证券化率+两融+ERP 主导；底部=恐慌(抓机会)：ERP+PB+证券化率 主导。
DEFAULT_WEIGHTS = {
    ("CN", "top"):    {"securitization": 0.25, "sentiment": 0.25, "erp": 0.20, "pe": 0.15, "pb": 0.15},
    ("CN", "bottom"): {"securitization": 0.22, "erp": 0.30, "pb": 0.28, "pe": 0.10, "sentiment": 0.10},
}


def _raw_indicators(data_root: str, refresh: bool) -> dict[str, pd.Series]:
    """5 个原始指标序列。sentiment=两融占比；securitization=证券化率(巴菲特指标)。"""
    from quantlab.datasources.macro_source import china_securitization
    sec = china_securitization(data_root, refresh)["ratio"].sort_index()
    sec = sec[~sec.index.duplicated(keep="last")].rename("securitization")
    return {
        "pe": vs.cn_market_pe(data_root, refresh),
        "pb": vs.cn_market_pb(data_root, refresh),
        "erp": vs.cn_erp(data_root, refresh),
        "sentiment": vs.cn_margin_ratio(data_root, refresh),
        "securitization": sec,
    }


def _winsorize_expanding(s: pd.Series, p: float = 0.01) -> pd.Series:
    """用扩张窗口分位裁剪极值，不引入未来函数（只用过去数据）。"""
    if p <= 0:
        return s
    lo = s.expanding(min_periods=20).quantile(p)
    hi = s.expanding(min_periods=20).quantile(1 - p)
    return s.clip(lower=lo, upper=hi)


def _aligned_pct(s: pd.Series, direction: str, mode: str, winsor: float = 0.01) -> pd.Series:
    """原值 → winsorize → 历史分位(0–100) → 按 mode/direction 对齐到温度分。

    顶部温度：越贵/越热分越高；底部温度：越便宜/越恐慌分越高（与顶部互补）。
    """
    pct = historical_percentile(_winsorize_expanding(s, winsor))
    hot = pct if direction == "high" else 100 - pct   # “越热”分（顶部语义）
    return hot if mode == "top" else 100 - hot


def _load_weights(market: str, mode: str, config_path: str | None) -> dict[str, float]:
    """优先读 config.yaml 的 thermometer 权重，缺失回退默认。"""
    if config_path and Path(config_path).exists():
        try:
            import yaml
            cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
            w = cfg.get("thermometer", {}).get(market.lower(), {}).get("weights", {}).get(mode)
            if w:
                return {k: float(v) for k, v in w.items()}
        except Exception:  # noqa: BLE001 —— 配置坏了就回退默认，不阻断
            pass
    return dict(DEFAULT_WEIGHTS[(market, mode)])


def compute_temperature(
    market: str = "CN",
    mode: str = "top",
    refresh: bool = False,
    data_root: str = "data/",
    config_path: str | None = "config.yaml",
    winsor: float = 0.01,
) -> pd.DataFrame:
    """市场温度（日度）。

    返回 DataFrame，index=date，列：
    - ``temperature``：0–100 综合温度
    - ``pct_<key>``  ：各指标对齐后的温度分位
    - ``contrib_<key>``：各指标对总温度的贡献（加总≈temperature）
    """
    if mode not in ("top", "bottom"):
        raise ValueError("mode 必须是 'top' 或 'bottom'")
    weights = _load_weights(market, mode, config_path)
    raw = _raw_indicators(data_root, refresh)

    pct = pd.DataFrame({
        f"pct_{k}": _aligned_pct(raw[k], DIRECTION[k], mode, winsor)
        for k in weights
    }).sort_index().ffill()

    w = pd.Series({f"pct_{k}": v for k, v in weights.items()})
    avail = pct[w.index].notna()
    wsum = avail.mul(w, axis=1).sum(axis=1)          # 各时点可用权重之和
    contrib = pct[w.index].mul(w, axis=1).div(wsum.replace(0, np.nan), axis=0)
    out = pct.copy()
    out["temperature"] = contrib.sum(axis=1, min_count=1)
    out = out.join(contrib.rename(columns=lambda c: c.replace("pct_", "contrib_")))
    return out[wsum > 0]


def net_temperature(
    market: str = "CN",
    refresh: bool = False,
    data_root: str = "data/",
    config_path: str | None = "config.yaml",
) -> pd.DataFrame:
    """顶部/底部/净温度三列（净 = 顶部 − 底部）。"""
    top = compute_temperature(market, "top", refresh, data_root, config_path)["temperature"]
    bot = compute_temperature(market, "bottom", False, data_root, config_path)["temperature"]
    df = pd.DataFrame({"top": top, "bottom": bot}).dropna()
    df["net"] = df["top"] - df["bottom"]
    return df
