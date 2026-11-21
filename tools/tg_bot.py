#!/usr/bin/env python3
"""用户 TG 账号 + 搜书机器人(@sobook) 的小封装。session 存 private/tl_session.txt（由 tdl 会话转换，见技能 ebook-audiobook-pipeline）。
子命令: send <文本>  | ls [n] | click <消息id> <按钮文字片段> | dl <消息id> <输出路径>
"""
import asyncio, sys
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
ROOT = Path(__file__).resolve().parent.parent
BOT = 'sobook'
def client():
    s = (ROOT / 'private/tl_session.txt').read_text().strip()
    return TelegramClient(StringSession(s), 2040, 'b18441a1ff607e10a989891a5462e627', proxy=('socks5', '127.0.0.1', 7897))
def show(m):
    print(f'#{m.id} {"ME" if m.out else "BOT"} file={m.file.name if m.file else None} size={m.file.size if m.file else None}')
    print('   ', (m.text or '')[:700].replace('\n', '\n    '))
    if m.buttons:
        for r in m.buttons: print('    [' + ' | '.join(b.text for b in r) + ']')
async def main():
    a = sys.argv[1:]; c = client(); await c.connect()
    if a[0] == 'send':
        await c.send_message(BOT, a[1]); await asyncio.sleep(float(a[2]) if len(a) > 2 else 5)
        for m in reversed([m async for m in c.iter_messages(BOT, limit=3)]): show(m)
    elif a[0] == 'ls':
        for m in reversed([m async for m in c.iter_messages(BOT, limit=int(a[1]) if len(a) > 1 else 5)]): show(m)
    elif a[0] == 'click':
        m = await c.get_messages(BOT, ids=int(a[1]))
        for r in m.buttons or []:
            for b in r:
                if a[2] in b.text: await b.click(); print('clicked', b.text); break
        await asyncio.sleep(4)
        for m in reversed([m async for m in c.iter_messages(BOT, limit=3)]): show(m)
    elif a[0] == 'dl':
        m = await c.get_messages(BOT, ids=int(a[1])); p = await c.download_media(m, a[2]); print(p)
    await c.disconnect()
asyncio.run(main())
