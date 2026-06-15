"""复权纯函数测试（task #5）—— 守住"复权纯函数 / 不缝合"不变量。"""

from __future__ import annotations

import pandas as pd

from quantlab.adjust import apply, compute_factors
from quantlab.constants import CLOSE
from quantlab.enums import Adjust
from tests.conftest import ohlcv


def _actions(idx, on, dividend=0.0, split=0.0):
    return pd.DataFrame({"dividend": dividend, "split": split}, index=[idx[on]])


def test_qfq_anchors_latest_hfq_anchors_first():
    raw = ohlcv([10, 10, 10, 10, 10])
    act = _actions(raw.index, on=2, dividend=1.0)   # 第3天除息 1 元
    af = compute_factors(act, raw)

    qfq = apply(raw, af, Adjust.QFQ)
    hfq = apply(raw, af, Adjust.HFQ)

    assert qfq[CLOSE].iloc[-1] == raw[CLOSE].iloc[-1]   # qfq 锚定最新
    assert hfq[CLOSE].iloc[0] == raw[CLOSE].iloc[0]     # hfq 锚定首日
    assert qfq[CLOSE].iloc[0] < raw[CLOSE].iloc[0]      # 早期被下调


def test_raw_passthrough():
    raw = ohlcv([10, 11, 12])
    out = apply(raw, compute_factors(None, raw), Adjust.RAW)
    assert (out[CLOSE] == raw[CLOSE]).all()


def test_append_does_not_restitch_hfq():
    raw = ohlcv([10, 10, 10, 10, 10])
    act = _actions(raw.index, on=2, dividend=1.0)
    hfq_before = apply(raw, compute_factors(act, raw), Adjust.HFQ)[CLOSE]

    raw2 = ohlcv([10, 10, 10, 10, 10, 11, 12])       # 追加两天新数据
    act2 = _actions(raw2.index, on=2, dividend=1.0)
    hfq_after = apply(raw2, compute_factors(act2, raw2), Adjust.HFQ)[CLOSE]

    # 早期 hfq 值不因新数据改变（无"缝合"）
    assert (hfq_after.iloc[:5].values == hfq_before.values).all()
