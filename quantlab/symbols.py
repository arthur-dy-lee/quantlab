"""统一代码 `Symbol` 与类型判定（详细设计 §4.2）。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from quantlab.enums import InstrumentType, Market
from quantlab.errors import SymbolParseError

# A股/港股 ETF 代码段（best-effort；source_hint 优先）
_CN_ETF_PREFIXES = ("51", "56", "58", "159", "15")
# 明确的指数代码（避免与个股 000001 等冲突，仅收录无歧义者）
_CN_INDEX_CODES = {"000300", "000905", "000016", "399006"}


@dataclass(frozen=True)
class Symbol:
    market: Market
    code: str
    instrument_type: InstrumentType = InstrumentType.UNKNOWN

    @classmethod
    def parse(cls, s: "str | Symbol") -> "Symbol":
        """``"CN:600519"`` → ``Symbol``；解析时 ``instrument_type`` 暂为 UNKNOWN。"""
        if isinstance(s, Symbol):
            return s
        if not isinstance(s, str) or ":" not in s:
            raise SymbolParseError(f"非法代码（缺少 '市场:' 前缀）: {s!r}")
        raw_market, _, code = s.partition(":")
        try:
            market = Market(raw_market.strip().upper())
        except ValueError as e:
            raise SymbolParseError(f"未知市场: {raw_market!r}（应为 {[m.value for m in Market]}）") from e
        code = code.strip()
        if not code:
            raise SymbolParseError(f"代码为空: {s!r}")
        return cls(market, code)

    @property
    def key(self) -> str:
        return f"{self.market.value}:{self.code}"

    def with_type(self, t: InstrumentType) -> "Symbol":
        return replace(self, instrument_type=t)

    def __str__(self) -> str:  # noqa: D105
        return self.key


def infer_instrument_type(
    market: Market, code: str, source_hint: str | None = None
) -> InstrumentType:
    """按市场 + 代码段 + 数据源标志位判定标的类型（详细设计 §4.2）。

    ``source_hint`` 优先（如 yfinance 的 quoteType）；A股靠代码段；crypto 恒为 CRYPTO。
    """
    if market == Market.CRYPTO:
        return InstrumentType.CRYPTO

    if source_hint:
        h = source_hint.strip().lower()
        if h == "etf":
            return InstrumentType.ETF
        if h == "index":
            return InstrumentType.INDEX
        if h in ("equity", "stock"):
            return InstrumentType.STOCK

    if market == Market.US:
        if code.startswith("^"):
            return InstrumentType.INDEX
        return InstrumentType.STOCK  # US 的 ETF 需 source_hint，否则默认按个股

    if market in (Market.CN, Market.HK):
        if code in _CN_INDEX_CODES:
            return InstrumentType.INDEX
        if any(code.startswith(p) for p in _CN_ETF_PREFIXES):
            return InstrumentType.ETF
        return InstrumentType.STOCK

    return InstrumentType.UNKNOWN
