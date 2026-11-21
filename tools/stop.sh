#!/bin/bash
# 精确停掉本项目的批处理（父子一起），不碰 tg_fetch/服务/隧道。用法: bash tools/stop.sh [build|tts|all]
case "${1:-all}" in
  build) pkill -f "tools/build_all.py" ;;
  tts)   pkill -f "tools/make_audio.py" ;;
  all)   pkill -f "tools/build_all.py"; pkill -f "tools/make_audio.py" ;;
esac
sleep 1; pgrep -fl "tools/(build_all|make_audio)" || echo "已停止"
