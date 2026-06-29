#!/bin/bash
# 统一调度器：单个 launchd 后台项，每15分钟(:00/:15/:30/:45)触发，
# 内部按"当前时间/星期"分派各任务。取代原先 dailyupdate/cnclose/gdp/indexalert 四个独立 plist。
# 由 launchd 触发：~/Library/LaunchAgents/com.quantlab.scheduler.plist
#
# 用 15 分钟「槽」判断而非精确分钟，以容忍 Mac 睡眠唤醒后补跑造成的时间漂移：
#   SLOT = 分钟/15 → 0(:00–14) 1(:15–29) 2(:30–44) 3(:45–59)

set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$PROJ" || exit 1

H=$((10#$(date +%H))); M=$((10#$(date +%M))); DOW=$(date +%u)
SLOT=$(( M / 15 ))

# ① 沪指大涨/大跌提醒：每30分钟(槽0、槽2)。交易时段/阈值/去重都在 index_alert.py 里。
if [ $SLOT -eq 0 ] || [ $SLOT -eq 2 ]; then
  /bin/bash "$PROJ/scripts/index_alert.sh"
fi

# ② 行情增量更新：每小时一次(槽0)。周日跳过(daily_update.sh 内部也会判)。
if [ $SLOT -eq 0 ] && [ $DOW -ne 7 ]; then
  /bin/bash "$PROJ/scripts/daily_update.sh"
fi

# ③ 宏观/估值周同步：每周六 10 点及以后首次调度，当天只跑一次(用 .gdp_done 去重，容忍唤醒漂移)。
if [ $DOW -eq 6 ] && [ $H -ge 10 ]; then
  STAMP="$PROJ/data/.gdp_done"
  if [ "$(cat "$STAMP" 2>/dev/null)" != "$(date +%F)" ]; then
    /bin/bash "$PROJ/scripts/gdp_update.sh" && date +%F > "$STAMP"
  fi
fi
