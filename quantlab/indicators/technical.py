"""技术指标（详细设计 §8.1）。默认自研（纯 Python）；装了 pandas-ta 也可走它（NFR-6）。"""

from __future__ import annotations

import re

import pandas as pd

from quantlab.constants import CLOSE, DEFAULT_INDICATORS, HIGH, LOW


def ma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False).mean()   # Wilder 平滑
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(s, fast) - ema(s, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def boll(s: pd.Series, n: int = 20, k: float = 2) -> pd.DataFrame:
    mid = s.rolling(n).mean()
    std = s.rolling(n).std(ddof=0)
    return pd.DataFrame({"boll_mid": mid, "boll_up": mid + k * std, "boll_low": mid - k * std})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, low, c = df[HIGH], df[LOW], df[CLOSE]
    prev_c = c.shift(1)
    tr = pd.concat([h - low, (h - prev_c).abs(), (low - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def add_indicators(df: pd.DataFrame, spec: list[str] | None = None) -> pd.DataFrame:
    """给 OHLCV 追加指标列（不改原列）。spec 默认 ``constants.DEFAULT_INDICATORS``。"""
    spec = spec or DEFAULT_INDICATORS
    out = df.copy()
    close = df[CLOSE]
    for name in spec:
        if name in out.columns:
            continue
        if m := re.fullmatch(r"ma(\d+)", name):
            out[name] = ma(close, int(m.group(1)))
        elif m := re.fullmatch(r"ema(\d+)", name):
            out[name] = ema(close, int(m.group(1)))
        elif m := re.fullmatch(r"rsi(\d+)", name):
            out[name] = rsi(close, int(m.group(1)))
        elif m := re.fullmatch(r"atr(\d+)", name):
            out[name] = atr(df, int(m.group(1)))
        elif name in ("macd", "macd_signal", "macd_hist"):
            if "macd" not in out.columns:
                out[["macd", "macd_signal", "macd_hist"]] = macd(close)
        elif name in ("boll_mid", "boll_up", "boll_low"):
            if "boll_mid" not in out.columns:
                out[["boll_mid", "boll_up", "boll_low"]] = boll(close)
    return out
