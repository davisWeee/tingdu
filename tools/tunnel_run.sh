#!/bin/bash
# launchd 常驻：启动 cloudflared 快速隧道，解析公网地址，拼出带令牌的听读链接；链接变化时用 hermes send 推送到 Telegram。
cd /Users/heyangyu/.hermes/projects/tingdu || exit 1
LOG=private/tunnel.log; : > "$LOG"
/Users/heyangyu/.hermes/tools/cloudflared/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8765 > "$LOG" 2>&1 &
CF=$!
trap 'kill $CF 2>/dev/null' TERM INT
URL=""
for i in $(seq 1 90); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1)
  [ -n "$URL" ] && break; sleep 1
done
if [ -n "$URL" ]; then
  echo "$URL" > private/tunnel_url.txt
  LINK="https://davisweee.github.io/tingdu/?lib=$URL/$(cat library-private/.token)/"
  echo "$LINK" > private/link.txt
  # 稳定入口：把最新隧道地址写进仓库的 pointer.json（不含令牌）并推送，页面据此自动找到书库
  printf '{"base":"%s","updated":"%s"}' "$URL" "$(date '+%Y-%m-%dT%H:%M:%S')" > pointer.json
  git add pointer.json && git commit -q -m "pointer: 隧道地址更新" && git -c http.proxy=socks5h://127.0.0.1:7897 push -q origin main || echo "pointer push failed"
  if [ "$(cat private/link_notified.txt 2>/dev/null)" != "$LINK" ]; then
    /Users/heyangyu/.local/bin/hermes send -t telegram -q "听读书库已自动切到新隧道（pointer 已推送，1-2 分钟后看板里的听读自动恢复）。若仍空书架，点页脚「连接私人书库」，粘贴钥匙：$(cat library-private/.token)" && echo "$LINK" > private/link_notified.txt
  fi
fi
wait $CF
