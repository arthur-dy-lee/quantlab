"""配置加载（详细设计 §4.3）—— yaml + ``${ENV}`` 插值。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from quantlab.enums import Adjust, Market
from quantlab.symbols import Symbol

_ENV_RE = re.compile(r"\$\{(\w+)\}")


@dataclass
class SizingConfig:
    method: str = "fixed_tier"          # fixed_tier | kelly_conservative
    max_position: float = 0.5
    kelly_fraction: float = 0.3


@dataclass
class NotifyConfig:
    channels: list[str] = field(default_factory=lambda: ["console"])
    feishu: dict = field(default_factory=dict)
    telegram: dict = field(default_factory=dict)
    email: dict = field(default_factory=dict)
    throttle_minutes: int = 30


@dataclass
class Config:
    data_root: str = "data/"
    offline_only: bool = False
    adjust_default: Adjust = Adjust.QFQ
    markets: dict[Market, dict] = field(default_factory=dict)
    watchlists: dict[str, list[Symbol]] = field(default_factory=dict)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    stats_min_samples: int = 30
    retry: dict = field(default_factory=lambda: {"retries": 3, "backoff": 1.5})

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        text = Path(path).read_text(encoding="utf-8")
        text = _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), text)  # 缺失 → 空串
        raw = yaml.safe_load(text) or {}

        markets = {Market(k): v for k, v in (raw.get("markets") or {}).items()}
        watchlists = {
            name: [Symbol.parse(s) for s in lst]
            for name, lst in (raw.get("watchlists") or {}).items()
        }
        return cls(
            data_root=raw.get("data_root", "data/"),
            offline_only=bool(raw.get("offline_only", False)),
            adjust_default=Adjust(raw.get("adjust_default", "qfq")),
            markets=markets,
            watchlists=watchlists,
            sizing=SizingConfig(**(raw.get("sizing") or {})),
            notify=NotifyConfig(**(raw.get("notify") or {})),
            stats_min_samples=int(raw.get("stats_min_samples", 30)),
            retry=raw.get("retry") or {"retries": 3, "backoff": 1.5},
        )
