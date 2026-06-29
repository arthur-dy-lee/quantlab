#!/usr/bin/env python3
"""多通道推送：把 <title> <content> 同时发到所有已配置的通道。

读环境变量决定发哪些（任一未配置则跳过该通道，互不影响）：
  PushPlus(个人微信): PUSHPLUS_TOKEN
  钉钉群机器人:       DINGTALK_WEBHOOK [+ DINGTALK_SECRET 加签]
  Bark(iOS 系统推送): BARK_URL   形如 https://api.day.app/你的key

仅用标准库(urllib)，不依赖 requests。被定时脚本 lib.sh 调用。
用法: python notify.py "标题" "正文"
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request


def _post_json(url: str, payload: dict) -> str:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 —— 固定通知域名
        return r.read().decode("utf-8", "ignore")[:200]


def push_pushplus(title: str, content: str) -> str:
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        return ""
    try:
        resp = _post_json("https://www.pushplus.plus/send",
                          {"token": token, "title": title, "content": content, "template": "txt"})
        return f"pushplus={resp}"
    except Exception as e:  # noqa: BLE001
        return f"pushplus-ERR={type(e).__name__}:{e}"


def push_dingtalk(title: str, content: str) -> str:
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    if not webhook:
        return ""
    secret = os.environ.get("DINGTALK_SECRET")
    url = webhook
    if secret:  # 加签：timestamp + "\n" + secret 做 HmacSHA256 → base64 → urlencode
        ts = str(round(time.time() * 1000))
        sign = urllib.parse.quote_plus(base64.b64encode(
            hmac.new(secret.encode(), f"{ts}\n{secret}".encode(), hashlib.sha256).digest()))
        url = f"{webhook}&timestamp={ts}&sign={sign}"
    try:
        resp = _post_json(url, {"msgtype": "text", "text": {"content": f"{title}\n{content}"}})
        return f"dingtalk={resp}"
    except Exception as e:  # noqa: BLE001
        return f"dingtalk-ERR={type(e).__name__}:{e}"


def push_bark(title: str, content: str) -> str:
    base = os.environ.get("BARK_URL")
    if not base:
        return ""
    try:
        url = f"{base.rstrip('/')}/{urllib.parse.quote(title)}/{urllib.parse.quote(content)}"
        with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310
            return f"bark={r.read().decode('utf-8', 'ignore')[:120]}"
    except Exception as e:  # noqa: BLE001
        return f"bark-ERR={type(e).__name__}:{e}"


def main() -> None:
    title = sys.argv[1] if len(sys.argv) > 1 else "QuantLab"
    content = sys.argv[2] if len(sys.argv) > 2 else ""
    results = [r for r in (push_pushplus(title, content),
                           push_dingtalk(title, content),
                           push_bark(title, content)) if r]
    print(" ; ".join(results) if results else "无已配置通道，跳过推送")


if __name__ == "__main__":
    main()
