"""全市场批量下载（OPT-3 并发）—— A股全量日线一次拉到本地。

并发取数 + 退避(with_retry 在 DataManager 内) + 断点续传(本地新鲜则跳过) + 进度日志。
对第三方免费源要"礼貌"：默认并发不高，失败的标的记日志跳过，不中断整轮。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from quantlab.enums import Freq
from quantlab.errors import SourceUnavailable
from quantlab.retry import with_retry

log = logging.getLogger("quantlab")


def list_cn_symbols(include_etf: bool = False) -> list[str]:
    """沪深京全部 A股代码（可选附 ETF）。"""
    try:
        import akshare as ak
    except ImportError as e:
        raise SourceUnavailable("akshare 未安装：pip install -e '.[cn]'") from e
    # 清单接口内部聚合沪深京，偶发某交易所超时 → 重试，避免整轮崩溃
    df = with_retry(lambda: ak.stock_info_a_code_name(), retries=4, backoff=2.0, on=(Exception,))
    syms = [f"CN:{c}" for c in df["code"].astype(str)]
    if include_etf:
        etf = with_retry(lambda: ak.fund_etf_spot_em(), retries=4, backoff=2.0, on=(Exception,))
        syms += [f"CN:{c}" for c in etf["代码"].astype(str)]
    # 去重保序
    seen: set[str] = set()
    return [s for s in syms if not (s in seen or seen.add(s))]


# ── 美股核心清单（curated）─────────────────────────────────────────────
# 七姐妹(Magnificent Seven)：苹果/微软/谷歌/亚马逊/Meta/英伟达/特斯拉
US_MEGACAP_TECH = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
# 纳指：纳斯达克综合 / 纳斯达克100（指数用 ^ 前缀，yfinance 原生）
US_INDEXES = ["^IXIC", "^NDX"]
# 科技/AI 主题 ETF：纳指100 / 科技板块 / 半导体×2 / 创新 / 机器人&AI / AI主题 / 软件
US_TECH_AI_ETFS = ["QQQ", "XLK", "SMH", "SOXX", "ARKK", "BOTZ", "AIQ", "IGV"]
# 注：SpaceX 为未上市私有公司、无公开股票代码，无法取数，故不在清单内。


def list_us_symbols() -> list[str]:
    """美股核心：七姐妹 + 纳指 + 科技/AI ETF（curated；不含未上市的 SpaceX）。"""
    return [f"US:{c}" for c in US_MEGACAP_TECH + US_INDEXES + US_TECH_AI_ETFS]


# ── 加密主流前十（参考币安市值排序、排除稳定币）──────────────────────────
# kraken 现货对：多数有 USDT；TRX 仅有 USD 对，故单列。
CRYPTO_TOP10 = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "TRX/USD", "AVAX/USDT", "LINK/USDT",
]


def list_crypto_symbols() -> list[str]:
    """主流加密前十（频率由调用方指定，本项目默认仅拉日线）。"""
    return [f"CRYPTO:{c}" for c in CRYPTO_TOP10]


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
