#!/bin/bash
# 定时任务共享库：环境、路径、日志、PushPlus(个人微信)推送。
# 各更新脚本开头 source 本文件即可。

export PATH="/Users/arthur.lee/miniforge3/bin:$PATH"
PROJ="/Users/arthur.lee/codes/quantlab"
QL="/Users/arthur.lee/miniforge3/bin/quantlab"
PY="/Users/arthur.lee/miniforge3/bin/python"
LOG="$PROJ/data/update.log"

# 秘钥(PUSHPLUS_TOKEN 等)放家目录、不入 git；launchd 不继承登录 shell 环境，故在此显式加载。
[ -f "$HOME/.quantlab.env" ] && . "$HOME/.quantlab.env"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

# pp_push <标题> <正文>  —— 多通道推送(PushPlus微信 / 钉钉 / Bark，配了哪个发哪个)。
# 实际逻辑在 scripts/notify.py；秘钥由本文件 source 的 ~/.quantlab.env 提供并 export。
pp_push() {
  local title="$1" content="$2" temp resp
  temp=$("$PY" "$PROJ/scripts/thermometer_line.py" 2>>"$LOG")   # 当前A股温度，算不出则空
  [ -n "$temp" ] && content="${content}
${temp}"
  resp=$("$PY" "$PROJ/scripts/notify.py" "$title" "$content" 2>>"$LOG")
  echo "[$(ts)] 推送: $resp" >> "$LOG"
}
