#!/usr/bin/env python3
"""Telegram 全局文件搜索（公开频道/群里的文档消息）。用法: python3 tools/tg_global.py "关键词" [条数]
输出: chat | 消息id | 文件名 | 大小 —— 可再用 download 子命令下载。注意：同一 auth key 不要并发多个客户端。"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tg_bot import client
from telethon.tl.types import InputMessagesFilterDocument
async def main():
    kw = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    c = client(); await c.connect()
    async for m in c.iter_messages(None, search=kw, filter=InputMessagesFilterDocument, limit=n):
        ch = getattr(m.chat, 'username', None) or getattr(m.chat, 'title', None) or m.chat_id
        print(f'{ch} | {m.id} | {m.file.name if m.file else None} | {(m.file.size or 0)//1024}KB')
    await c.disconnect()
asyncio.run(main())
