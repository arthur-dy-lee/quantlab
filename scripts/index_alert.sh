#!/bin/bash
# 上证大涨/大跌盘中提醒：盘中每15分钟由 launchd 触发。
# index_alert.py 判定(交易时段+阈值+当日去重)，命中才输出 "标题\t正文"，再经 pp_push 推送(自动附温度)。
# 由 launchd 触发：~/Library/LaunchAgents/com.quantlab.indexalert.plist

set -uo pipefail
source "$(dirname "$0")/lib.sh"
cd "$PROJ" || exit 1

out=$("$PY" scripts/index_alert.py 2>>"$LOG")
[ -z "$out" ] && exit 0          # 非交易时段 / 未超阈 / 今日已报 → 静默

title="${out%%$'\t'*}"
body="${out#*$'\t'}"
echo "[$(ts)] 指数提醒触发: $title | $body" >> "$LOG"
pp_push "$title" "$body"
