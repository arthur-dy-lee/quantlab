"""跨模块共享的常量（详细设计 §1、§13.2）。"""

from __future__ import annotations

# 标准 OHLCV 列名
OPEN = "open"
HIGH = "high"
LOW = "low"
CLOSE = "close"
VOLUME = "volume"
OHLCV = [OPEN, HIGH, LOW, CLOSE, VOLUME]
PRICE_COLS = [OPEN, HIGH, LOW, CLOSE]  # 复权时按比例调整，volume 不调

# DatetimeIndex 名称
DATE = "date"

# add_indicators 默认追加的列（详细设计 §13.2）
DEFAULT_INDICATORS = [
    "ma5",
    "ma20",
    "ema12",
    "rsi14",
    "macd",
    "macd_signal",
    "macd_hist",
    "boll_mid",
    "boll_up",
    "boll_low",
    "atr14",
]
