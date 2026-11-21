#!/usr/bin/env python3
"""按 books20.json 逐本从 @sobook 下载（/start book_<hash> → 文件消息 → download_media）。已存在则跳过。
用法: python3 tools/tg_fetch.py tools/books20.json [id1,id2..]"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tg_bot import client, BOT, ROOT
async def main():
    books = json.load(open(sys.argv[1])); only = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else None
    out = ROOT / 'private/books'; out.mkdir(parents=True, exist_ok=True)
    c = client(); await c.connect()
    for b in books:
        if only and b['id'] not in only: continue
        last = (await c.get_messages(BOT, limit=1))[0].id
        doc = None
        for attempt in range(4):
            await c.send_message(BOT, f"/start book_{b['hash']}")
            for _ in range(15):
                await asyncio.sleep(2)
                ms = [m async for m in c.iter_messages(BOT, limit=6) if m.id > last and not m.out]
                d = [m for m in ms if m.file]; t = [m for m in ms if m.text and ('额度' in m.text or '不足' in m.text or '上限' in m.text)]
                if d: doc = d[0]; break
                if t: print('  bot says:', t[0].text[:200]); break
            if doc or (t if 't' in dir() and t else None): break
            await asyncio.sleep(4)
        if not doc: print('FAIL', b['id']); continue
        name = doc.file.name or ''; ext = (name.rsplit('.', 1)[-1] if '.' in name else 'bin').lower()
        tgt = out / f"{b['id']}.{ext}"
        if tgt.exists() and tgt.stat().st_size == doc.file.size: print('skip(已完整)', b['id']); continue
        p = await c.download_media(doc, str(tgt))
        print('OK', b['id'], p, doc.file.size, flush=True)
        await asyncio.sleep(3)
    await c.disconnect()
asyncio.run(main())
