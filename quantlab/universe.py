"""全市场批量下载（OPT-3 并发）—— A股全量日线一次拉到本地。

并发取数 + 退避(with_retry 在 DataManager 内) + 断点续传(本地新鲜则跳过) + 进度日志。
对第三方免费源要"礼貌"：默认并发不高，失败的标的记日志跳过，不中断整轮。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from quantlab.enums import Freq
from quantlab.errors import SourceUnavailable

log = logging.getLogger("quantlab")


def list_cn_symbols(include_etf: bool = False) -> list[str]:
    """沪深京全部 A股代码（可选附 ETF）。"""
    try:
        import akshare as ak
    except ImportError as e:
        raise SourceUnavailable("akshare 未安装：pip install -e '.[cn]'") from e
    df = ak.stock_info_a_code_name()          # columns: code, name
    syms = [f"CN:{c}" for c in df["code"].astype(str)]
    if include_etf:
        etf = ak.fund_etf_spot_em()           # column: 代码
        syms += [f"CN:{c}" for c in etf["代码"].astype(str)]
    # 去重保序
    seen: set[str] = set()
    return [s for s in syms if not (s in seen or seen.add(s))]


def download_universe(
    dm,
    symbols: list[str],
    workers: int = 8,
    freq: Freq = Freq.DAY,
    progress_every: int = 200,
) -> dict:
    """并发下载一篮子标的到本地缓存。返回 {total, ok, fail, failed:[...]}。"""
    total = len(symbols)
    ok = 0
    failed: list[str] = []

    def task(sym: str) -> None:
        dm.history(sym, freq=freq)            # 下载+落盘；本地新鲜则内部跳过联网

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(task, s): s for s in symbols}
        for i, fut in enumerate(as_completed(futs), 1):
            sym = futs[fut]
            try:
                fut.result()
                ok += 1
            except Exception as e:  # noqa: BLE001 —— 单标的失败不中断
                failed.append(sym)
                log.warning("universe 下载失败 %s: %s", sym, e)
            if i % progress_every == 0 or i == total:
                log.info("进度 %d/%d  ok=%d fail=%d", i, total, ok, len(failed))

    return {"total": total, "ok": ok, "fail": len(failed), "failed": failed}
