#!/bin/bash
# 宏观/估值周同步(每周六)：低频指标，一周刷一次足够。
#   - GDP/巴菲特指数(证券化率) CN+US  → macro_source
#   - 市场温度计估值指标 CN：全市场PE/PB、沪深300PE、10年国债、两融余额 → valuation_source
# 全部 refresh=True 联网刷新并落 data/macro/*.parquet。逐项独立 try，一个失败不影响其余。
# 由 launchd 触发：~/Library/LaunchAgents/com.quantlab.gdp.plist

set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$PROJ" || exit 1

echo "[$(ts)] ===== 宏观/估值周同步开始 =====" >> "$LOG"

out=$("$PY" - <<'PY' 2>>"$LOG"
from quantlab.datasources.macro_source import china_securitization, us_securitization
from quantlab.datasources import valuation_source as vs

jobs = [
    ("巴菲特CN", lambda: china_securitization(refresh=True)),
    ("巴菲特US", lambda: us_securitization(refresh=True)),
    ("全市场PE", lambda: vs.cn_market_pe(refresh=True)),
    ("全市场PB", lambda: vs.cn_market_pb(refresh=True)),
    ("沪深300PE", lambda: vs.cn_csi300_pe(refresh=True)),
    ("10年国债", lambda: vs.cn_bond_10y(refresh=True)),
    ("两融SH", lambda: vs.cn_margin_sh(refresh=True)),
]
ok = fail = 0
parts = []
for name, fn in jobs:
    try:
        d = fn()
        ok += 1
        parts.append(f"{name}✓{len(d)}")
    except Exception as e:
        fail += 1
        parts.append(f"{name}✗{type(e).__name__}")
print(f"ok={ok} fail={fail} | " + " ".join(parts))
PY
)
echo "$out" >> "$LOG"
echo "[$(ts)] ===== 周同步完成 =====" >> "$LOG"
pp_push "QuantLab 宏观/估值周同步 $(date '+%m-%d')" "${out:-无结果}"
