"""仓位建议（详细设计 §8.3）—— 无统计优势/不可靠 → 0（P-6/P-7）。"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from quantlab.stats.probability import ProbabilityResult


class PositionSizer(ABC):
    def __init__(self, max_position: float = 0.5) -> None:
        self.max_position = max_position

    def _guard(self, r: ProbabilityResult) -> bool:
        return r.reliable and r.edge > 0

    @abstractmethod
    def size(self, r: ProbabilityResult) -> float:
        ...


class FixedTierSizer(PositionSizer):
    """p_up 映射档位：>=0.70→0.5, >=0.65→0.3, >=0.60→0.1, else 0（截到 max_position）。"""

    def size(self, r: ProbabilityResult) -> float:
        if not self._guard(r):
            return 0.0
        p = r.p_up
        base = 0.5 if p >= 0.70 else 0.3 if p >= 0.65 else 0.1 if p >= 0.60 else 0.0
        return min(base, self.max_position)


class KellyConservativeSizer(PositionSizer):
    """f=(b·p-(1-p))/b，乘保守系数并截到 [0, max_position]。"""

    def __init__(self, max_position: float = 0.5, kelly_fraction: float = 0.3) -> None:
        super().__init__(max_position)
        self.kelly_fraction = kelly_fraction

    def size(self, r: ProbabilityResult) -> float:
        if not self._guard(r):
            return 0.0
        b, p = r.payoff, r.p_up
        f = 1.0 if not math.isfinite(b) or b <= 0 else (b * p - (1 - p)) / b
        f = max(0.0, f) * self.kelly_fraction
        return min(f, self.max_position)


def build_sizer(cfg) -> PositionSizer:
    """按 config.sizing.method 构造仓位器。"""
    s = cfg.sizing
    if s.method == "kelly_conservative":
        return KellyConservativeSizer(s.max_position, s.kelly_fraction)
    return FixedTierSizer(s.max_position)
