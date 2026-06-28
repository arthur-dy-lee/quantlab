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

# pp_push <标题> <正文>  —— 推送到个人微信(PushPlus 公众号)。未配置 token 则静默跳过。
pp_push() {
  local title="$1" content="$2"
  [ -z "${PUSHPLUS_TOKEN:-}" ] && { echo "[$(ts)] PUSHPLUS_TOKEN 未配置，跳过推送" >> "$LOG"; return 0; }
  # 用 python 安全地构造 JSON(避免正文里的引号/换行破坏 payload)
  local payload
  payload=$("$PY" -c 'import json,sys; print(json.dumps({"token":sys.argv[1],"title":sys.argv[2],"content":sys.argv[3],"template":"txt"}))' \
    "$PUSHPLUS_TOKEN" "$title" "$content")
  local resp
  resp=$(curl -s -m 10 -X POST https://www.pushplus.plus/send \
    -H 'Content-Type: application/json' -d "$payload")
  echo "[$(ts)] 推送结果: $resp" >> "$LOG"
}
