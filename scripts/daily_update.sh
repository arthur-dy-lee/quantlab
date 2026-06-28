#!/bin/bash
# 每日增量更新：A股全量 + 美股核心(七姐妹/纳指/科技AI ETF) + 加密前十。
# 清单见 quantlab download-all（--market CN/US/CRYPTO 已按市场精选）；
# download 内部带增量：本地新鲜则跳过联网，只补缺/补新，不会全量重下。
#
# 由 launchd 每天 11:30(上海时区)触发：~/Library/LaunchAgents/com.quantlab.dailyupdate.plist
# 11:30 时点：美东前一交易日已收盘 → 抓到隔夜美股；周六也跑(抓周五美股收盘)。周日休市跳过。
# 注意：A股 15:00 才收盘，11:30 只能取到「上一交易日」终值；当日 A股收盘由 cn_close_update.sh(15:05)负责。

set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$PROJ" || exit 1

# date +%u: 1=周一 … 7=周日。周日休市不更新。
if [ "$(date +%u)" -eq 7 ]; then
  echo "[$(ts)] 周日休市，跳过" >> "$LOG"
  exit 0
fi

echo "[$(ts)] ===== 每日增量更新开始 (周$(date +%u)) =====" >> "$LOG"

SUMMARY=""
run() {  # $1 = market (CN|US|CRYPTO)
  local M="$1" out line
  echo "[$(ts)] 更新 $M …" >> "$LOG"
  out=$("$QL" download-all --market "$M" 2>>"$LOG")
  echo "$out" >> "$LOG"
  line=$(echo "$out" | grep -oE 'ok=[0-9]+ fail=[0-9]+ / [0-9]+' | tail -1)
  SUMMARY="${SUMMARY}${M}: ${line:-无结果} | "
  echo "[$(ts)] $M 完成" >> "$LOG"
}

run CN
run US
run CRYPTO   # 仅前十、需求不大；若不想每天更新加密，注释掉这一行即可

echo "[$(ts)] ===== 完成 =====" >> "$LOG"
pp_push "QuantLab 行情更新 $(date '+%m-%d %H:%M')" "$SUMMARY"
