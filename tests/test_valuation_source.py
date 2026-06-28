"""市场温度计取数层冒烟测试（联网，标 network）。

校验每个 akshare 取数函数：返回非空、index 为单调递增且无重复日期。
用 -m 'not network' 可跳过。
"""

from __future__ import annotations

import pandas as pd
import pytest

from quantlab.datasources import valuation_source as vs

pytestmark = pytest.mark.network

_FETCHERS = [
    "cn_market_pe", "cn_market_pb", "cn_csi300_pe",
    "cn_bond_10y", "cn_margin_sh", "cn_total_mktcap",
    "cn_erp", "cn_margin_ratio",
]


@pytest.mark.parametrize("name", _FETCHERS)
def test_fetcher_schema(name):
    s = getattr(vs, name)()              # 命中缓存即可，不强制 refresh
    assert isinstance(s, pd.Series)
    assert len(s) > 100
    assert s.index.is_monotonic_increasing
    assert s.index.duplicated().sum() == 0
    assert s.notna().all()


def test_erp_definition():
    """ERP = 沪深300盈利收益率(1/PE×100) − 10年国债，应在合理区间。"""
    erp = vs.cn_erp()
    assert -5 < erp.iloc[-1] < 15        # 历史上大致 -2%~10%
