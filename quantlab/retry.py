"""重试退避（详细设计 §2）—— 仅包 FetchError，耗尽后抛出由调用方记日志。"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

from quantlab.errors import FetchError

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    retries: int = 3,
    backoff: float = 1.5,
    on: tuple[type[Exception], ...] = (FetchError,),
) -> T:
    last: Exception | None = None
    for i in range(retries):
        try:
            return fn()
        except on as e:  # type: ignore[misc]
            last = e
            if i < retries - 1:
                time.sleep(backoff**i)
    assert last is not None
    raise last
