"""市场 → 数据源 路由 + 实例缓存（详细设计 §5.5）。"""

from __future__ import annotations

from quantlab.config import Config
from quantlab.datasources.base import DataSource
from quantlab.enums import Market
from quantlab.errors import SourceUnavailable


class SourceRegistry:
    def __init__(self, config: Config) -> None:
        self._cfg = config
        self._cache: dict[Market, DataSource] = {}

    def get_source(self, market: Market) -> DataSource:
        if market in self._cache:
            return self._cache[market]
        spec = self._cfg.markets.get(market)
        if not spec:
            raise SourceUnavailable(f"未配置市场 {market} 的数据源")
        name = spec.get("source") if isinstance(spec, dict) else spec
        src = self._build(name, spec if isinstance(spec, dict) else {})
        self._cache[market] = src
        return src

    @staticmethod
    def _build(name: str, spec: dict) -> DataSource:
        if name == "yfinance":
            from quantlab.datasources.yfinance_source import YFinanceSource
            return YFinanceSource()
        if name == "akshare":
            from quantlab.datasources.akshare_source import AkshareSource
            return AkshareSource()
        if name == "ccxt":
            from quantlab.datasources.ccxt_source import CcxtSource
            return CcxtSource(exchange=spec.get("exchange", "kraken"))
        raise SourceUnavailable(f"未知数据源: {name}")
