#!/usr/bin/env python3
"""批量在 @sobook 搜书，打印每个关键词的前 N 个结果（标题/格式/大小/字数/hash）。
用法: python3 tools/tg_search.py 关键词1 关键词2 ... [--n 6]"""
import asyncio, re, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from tg_bot import client, BOT
async def main():
    args = sys.argv[1:]; n = 6
    if '--n' in args: i = args.index('--n'); n = int(args[i + 1]); del args[i:i + 2]
    c = client(); await c.connect()
    for kw in args:
        last = (await c.get_messages(BOT, limit=1))[0].id
        await c.send_message(BOT, kw)
        res = None
        for _ in range(12):
            await asyncio.sleep(2)
            ms = [m async for m in c.iter_messages(BOT, limit=4) if m.id > last and not m.out]
            ms = [m for m in ms if m.text and 'book_' in m.text]
            if ms: res = ms[0]; break
        print(f'=== {kw}')
        if not res: print('  (无结果/超时)'); continue
        t = res.text
        for mt in re.finditer(r'`(\d+)\.`\[(.*?)\]\(https://t\.me/sosdbot\?start=book_(\w+)\)\s*\n?\s*`(.*?)`', t):
            if int(mt.group(1)) <= n: print(f'  {mt.group(1)}. {mt.group(2)[:50]} | {mt.group(4)} | {mt.group(3)}')
        await asyncio.sleep(1.5)
    await c.disconnect()
asyncio.run(main())
