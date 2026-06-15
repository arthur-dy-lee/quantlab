"""基本面筛选（详细设计 FR-5.2 / M3）—— 接口 + akshare provider（best-effort）。

ETF/指数无个股基本面 → 由 Screener 的 applicable_types 跳过（见 screener.py）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from quantlab.enums import InstrumentType, Market
from quantlab.errors import FetchError, SourceUnavailable
from quantlab.symbols import Symbol

_STOCK = {InstrumentType.STOCK}


@dataclass
class FundamentalRule:
    """对基本面字典(PE/PB/ROE…)求值的规则；仅个股适用。"""

    name: str
    predicate: Callable[[dict], bool]
    applicable_types: frozenset = frozenset(_STOCK)


class FundamentalProvider:
    """取个股 PE/PB/ROE 等（akshare，懒加载、best-effort）。"""

    def get(self, symbol: str) -> dict:
        sym = Symbol.parse(symbol)
        if sym.market not in (Market.CN, Market.HK):
            raise FetchError(f"暂仅支持 A股/港股基本面: {symbol}")
        try:
            import akshare as ak
        except ImportError as e:
            raise SourceUnavailable("akshare 未安装：pip install -e '.[cn]'") from e
        try:
            df = ak.stock_a_indicator_lg(symbol=sym.code)  # PE/PB/股息率等历史
            last = df.iloc[-1]
            return {"pe": float(last.get("pe_ttm", "nan")), "pb": float(last.get("pb", "nan"))}
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"akshare 基本面取数失败 {symbol}: {e}") from e


# 示例规则
def pe_lt(x: float) -> FundamentalRule:
    return FundamentalRule(f"PE<{x:g}", lambda f: f.get("pe", float("inf")) < x)


def pb_lt(x: float) -> FundamentalRule:
    return FundamentalRule(f"PB<{x:g}", lambda f: f.get("pb", float("inf")) < x)
