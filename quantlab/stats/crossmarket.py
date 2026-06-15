"""跨市场领先预警（详细设计 §8.3 / 12.3）—— 美股 → A股。M2。

TODO(task #M2): 用 calendar.align(lead, target, lag=1) 对齐后复用 probability。
"""

from __future__ import annotations

from quantlab.stats.conditions import Condition
from quantlab.stats.probability import ProbabilityResult


def crossmarket(
    dm,
    lead: str,
    target: str,
    cond: Condition,
    forward: int = 1,
    calendar=None,
) -> ProbabilityResult:
    raise NotImplementedError("TODO(M2): crossmarket")
