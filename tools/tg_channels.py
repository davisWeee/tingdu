#!/usr/bin/env python3
"""搜公开频道/群（按名字），并可在其中搜文件：python3 tools/tg_channels.py 电子书 [--in 频道 关键词]"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tg_bot import client
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import InputMessagesFilterDocument
async def main():
    a = sys.argv[1:]; c = client(); await c.connect()
    if a[0] == '--in':
        async for m in c.iter_messages(a[1], search=a[2], filter=InputMessagesFilterDocument, limit=8):
            print(f'{m.id} | {m.file.name} | {(m.file.size or 0)//1024}KB')
    else:
        r = await c(SearchRequest(q=a[0], limit=20))
        for ch in r.chats: print(f'@{getattr(ch,"username",None)} | {ch.title} | {getattr(ch,"participants_count",None)}')
    await c.disconnect()
asyncio.run(main())
