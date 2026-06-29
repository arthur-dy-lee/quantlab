#!/bin/bash
# 统一调度器：单个 launchd 后台项，每15分钟(:00/:15/:30/:45)+ 15:05 触发，
# 内部按"当前时间/星期"分派 4 个任务。取代原先 dailyupdate/cnclose/gdp/indexalert 四个独立 plist。
# 由 launchd 触发：~/Library/LaunchAgents/com.quantlab.scheduler.plist
#
# 忠实复刻 4 个原任务的定时与语义：
#   ① 沪指大涨/大跌提醒  每15分钟(每次唤醒)；交易时段 / ±1%阈值 / 当日每方向去重 都在 index_alert.py 内。
#   ② 行情增量更新       每天 11:30 一次(周日跳过)；CN+US+CRYPTO。       —— 原 dailyupdate
#   ③ A股收盘更新        每天 15:05 一次(周末跳过)；仅 CN。              —— 原 cnclose
#   ④ 宏观/估值周同步     每周六 一次(首个 ≥10:00 的唤醒)。              —— 原 gdp
#
# ②③④ 用「当天首个达到目标时刻的唤醒才跑 + 当日去重戳」实现：
#   - 每天只跑一次(戳文件记当天日期，跑过即写)；
#   - 容忍 Mac 睡眠唤醒后的时间漂移：醒来后的首个唤醒会补跑当天遗漏的任务，
#     这与原先每个独立 plist 在睡眠后被 launchd 补跑一次的行为等价。

set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$PROJ" || exit 1

H=$((10#$(date +%H))); M=$((10#$(date +%M))); DOW=$(date +%u); TODAY=$(date +%F)
NOW=$((H * 60 + M))   # 当前「分钟数(0–1439)」，便于与目标时刻比较

done_today() { [ "$(cat "$1" 2>/dev/null)" = "$TODAY" ]; }   # 戳内容==今天 ⇒ 今日已跑

# ① 沪指提醒：每次唤醒都跑(= 每15分钟)。非交易时段 index_alert.py 会在联网前即时静默，几乎零开销。
/bin/bash "$PROJ/scripts/index_alert.sh"

# ② 行情增量更新：当天首个 ≥11:30 的唤醒跑一次；周日(DOW=7)跳过。跑成功才写戳，失败则下个唤醒重试。
if [ "$DOW" -ne 7 ] && [ "$NOW" -ge $((11 * 60 + 30)) ] && ! done_today "$PROJ/data/.dailyupdate_done"; then
  /bin/bash "$PROJ/scripts/daily_update.sh" && echo "$TODAY" > "$PROJ/data/.dailyupdate_done"
fi

# ③ A股收盘更新：当天首个 ≥15:05 的唤醒跑一次；周末(DOW≥6)跳过。
if [ "$DOW" -le 5 ] && [ "$NOW" -ge $((15 * 60 + 5)) ] && ! done_today "$PROJ/data/.cnclose_done"; then
  /bin/bash "$PROJ/scripts/cn_close_update.sh" && echo "$TODAY" > "$PROJ/data/.cnclose_done"
fi

# ④ 宏观/估值周同步：周六(DOW=6)首个 ≥10:00 的唤醒跑一次。
if [ "$DOW" -eq 6 ] && [ "$NOW" -ge $((10 * 60)) ] && ! done_today "$PROJ/data/.gdp_done"; then
  /bin/bash "$PROJ/scripts/gdp_update.sh" && echo "$TODAY" > "$PROJ/data/.gdp_done"
fi
