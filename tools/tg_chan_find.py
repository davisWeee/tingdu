#!/usr/bin/env python3
"""在给定公开频道里按书名找文件，列出文件名含书名的候选（epub 优先）。
用法: python3 tools/tg_chan_find.py <频道> 书名1 书名2 ..."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tg_bot import client
from telethon.tl.types import InputMessagesFilterDocument
RANK = {'epub': 0, 'azw3': 1, 'mobi': 2, 'txt': 3, 'pdf': 9}
async def main():
    ch = sys.argv[1]; c = client(); await c.connect()
    for k in sys.argv[2:]:
        print('==', k)
        seen = []
        async for m in c.iter_messages(ch, search=k, filter=InputMessagesFilterDocument, limit=30):
            n = m.file.name or ''
            if k[:3] in n or k in n: seen.append((RANK.get(n.rsplit('.', 1)[-1].lower(), 5), m.id, n, (m.file.size or 0) // 1024))
        for r in sorted(seen)[:5]: print(f'  {r[1]} | {r[2][:60]} | {r[3]}KB')
        await asyncio.sleep(1)
    await c.disconnect()
asyncio.run(main())
