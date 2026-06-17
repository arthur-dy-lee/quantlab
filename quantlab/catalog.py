"""标的名称库 + 收藏（看板用）。

名称库缓存到 data/names.parquet（A股/ETF 名称来自 akshare；US/加密 以代码为名）。
收藏存 data/favorites.json。两者都本地、轻量。
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


# 常用指数（用交易所前缀，避免与个股代码冲突）
KNOWN_INDEX = {
    "CN:sh000001": "上证指数", "CN:sh000300": "沪深300指数",
    "CN:sz399001": "深证成指", "CN:sz399006": "创业板指",
    "CN:sh000016": "上证50", "CN:sh000905": "中证500", "CN:sh000688": "科创50",
}

# 美股 curated 中文名（含常用别名，便于看板按中文/简称搜索；与 universe 清单对应）
KNOWN_NAMES_US = {
    "US:^IXIC": "纳斯达克综合指数(纳指)", "US:^NDX": "纳斯达克100指数(纳指100)",
    "US:AAPL": "苹果", "US:MSFT": "微软", "US:GOOGL": "谷歌Alphabet",
    "US:AMZN": "亚马逊", "US:META": "Meta(脸书)", "US:NVDA": "英伟达", "US:TSLA": "特斯拉",
    "US:QQQ": "纳指100ETF", "US:XLK": "美股科技板块ETF",
    "US:SMH": "半导体ETF(VanEck)", "US:SOXX": "半导体ETF(iShares)",
    "US:ARKK": "ARK创新ETF", "US:BOTZ": "机器人与AI ETF",
    "US:AIQ": "人工智能与科技ETF", "US:IGV": "软件ETF",
}

# 主流加密 curated 中文名（含别名/英文，便于搜索）
KNOWN_NAMES_CRYPTO = {
    "CRYPTO:BTC/USDT": "比特币BTC", "CRYPTO:ETH/USDT": "以太坊ETH",
    "CRYPTO:BNB/USDT": "币安币BNB", "CRYPTO:SOL/USDT": "Solana索拉纳SOL",
    "CRYPTO:XRP/USDT": "瑞波币XRP", "CRYPTO:DOGE/USDT": "狗狗币DOGE",
    "CRYPTO:ADA/USDT": "艾达币Cardano", "CRYPTO:TRX/USD": "波场TRON",
    "CRYPTO:AVAX/USDT": "Avalanche雪崩AVAX", "CRYPTO:LINK/USDT": "Chainlink预言机LINK",
}


def _names_path(root: str) -> Path:
    return Path(root) / "names.parquet"


def _fav_path(root: str) -> Path:
    return Path(root) / "favorites.json"


def load_names(root: str) -> dict[str, str]:
    p = _names_path(root)
    if not p.exists():
        return {}
    df = pd.read_parquet(p)
    return dict(zip(df["symbol"], df["name"]))


def build_names(dm) -> dict[str, str]:
    """拉取 A股/ETF 名称 + 本地已缓存标的，落盘并返回 {symbol: name}。"""
    from quantlab.retry import with_retry

    names: dict[str, str] = {}
    try:
        import akshare as ak

        st = with_retry(lambda: ak.stock_info_a_code_name(), retries=4, backoff=2.0, on=(Exception,))
        names.update({f"CN:{c}": n for c, n in zip(st["code"].astype(str), st["name"].astype(str))})
        etf = with_retry(lambda: ak.fund_etf_spot_em(), retries=4, backoff=2.0, on=(Exception,))
        names.update({f"CN:{c}": n for c, n in zip(etf["代码"].astype(str), etf["名称"].astype(str))})
    except Exception:  # noqa: BLE001 —— 无网/无 akshare 时退化为仅代码
        pass

    names.update(KNOWN_INDEX)            # 常用指数名
    names.update(KNOWN_NAMES_US)         # 美股 curated 中文名
    names.update(KNOWN_NAMES_CRYPTO)     # 加密 curated 中文名

    for m in dm.catalog():               # 本地已缓存的补全（无 curated 名则退化为代码）
        names.setdefault(m.symbol, m.symbol.split(":", 1)[1])

    df = pd.DataFrame({"symbol": list(names), "name": list(names.values())})
    df.to_parquet(_names_path(dm.cfg.data_root))
    return names


def load_favorites(root: str) -> list[str]:
    p = _fav_path(root)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_favorites(root: str, favs: list[str]) -> None:
    _fav_path(root).write_text(json.dumps(favs, ensure_ascii=False), encoding="utf-8")


def toggle_favorite(root: str, sym: str) -> list[str]:
    favs = load_favorites(root)
    favs.remove(sym) if sym in favs else favs.append(sym)
    save_favorites(root, favs)
    return favs
