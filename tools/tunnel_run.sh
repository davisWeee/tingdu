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
  if [ "$(cat private/link_notified.txt 2>/dev/null)" != "$LINK" ]; then
    /Users/heyangyu/.local/bin/hermes send -t telegram -q "听读书库链接已更新（隧道重启）：$LINK" && echo "$LINK" > private/link_notified.txt
  fi
fi
wait $CF
