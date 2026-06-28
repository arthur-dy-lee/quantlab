#!/bin/bash
# A股当日收盘增量更新：15:05(上海时区)A股已收盘(15:00)，此时抓到「当日」终值。
# 只更新 CN，美股/加密由 daily_update.sh(11:30)负责。周六/周日 A股休市跳过。
# 由 launchd 触发：~/Library/LaunchAgents/com.quantlab.cnclose.plist

set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$PROJ" || exit 1

# date +%u: 1=周一 … 6=周六 7=周日。周末 A股休市。
if [ "$(date +%u)" -ge 6 ]; then
  echo "[$(ts)] 周末 A股休市，跳过收盘更新" >> "$LOG"
  exit 0
fi

echo "[$(ts)] ===== A股收盘更新开始 (周$(date +%u)) =====" >> "$LOG"
out=$("$QL" download-all --market CN 2>>"$LOG")
echo "$out" >> "$LOG"
line=$(echo "$out" | grep -oE 'ok=[0-9]+ fail=[0-9]+ / [0-9]+' | tail -1)
echo "[$(ts)] A股收盘更新完成" >> "$LOG"
pp_push "QuantLab A股收盘 $(date '+%m-%d')" "CN: ${line:-无结果}"
