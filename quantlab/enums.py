"""枚举定义（详细设计 §4.1）。"""

from __future__ import annotations

from enum import Enum


class Market(str, Enum):
    CN = "CN"
    US = "US"
    HK = "HK"
    CRYPTO = "CRYPTO"


class InstrumentType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    CRYPTO = "crypto"
    UNKNOWN = "unknown"


class Adjust(str, Enum):
    RAW = "raw"
    QFQ = "qfq"
    HFQ = "hfq"


class Freq(str, Enum):
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"
    HOUR = "1h"
    MIN = "1m"
