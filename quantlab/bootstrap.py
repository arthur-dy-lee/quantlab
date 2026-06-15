"""依赖注入入口（详细设计 §7.3）。CLI / dashboard / notebook 都用 build_app() 取 DataManager。"""

from __future__ import annotations

from quantlab.calendar import TradingCalendar
from quantlab.config import Config
from quantlab.data_manager import DataManager
from quantlab.datasources.registry import SourceRegistry
from quantlab.storage.repository import BarRepository


def build_app(config_path: str = "config.yaml") -> DataManager:
    cfg = Config.load(config_path)
    return DataManager(
        cfg,
        BarRepository(cfg.data_root),
        SourceRegistry(cfg),
        TradingCalendar(),
    )
