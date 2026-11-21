#!/usr/bin/env python3
"""验证「公开 Pages 应用 + 私人书库隧道」整条链路：python3 tools/e2e_remote.py <应用URL> <书库URL> [书名关键字]"""
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
app, lib = sys.argv[1], sys.argv[2]; key = sys.argv[3] if len(sys.argv) > 3 else '李大霄'
CHROME = str(next(Path.home().glob('.hermes/tools/chromium-*/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing')))
OUT = Path(__file__).resolve().parent.parent / 'private' / 'shots'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True, args=['--autoplay-policy=no-user-gesture-required'])
    pg = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True).new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'{app}?lib={lib}'); time.sleep(5)
    names = pg.locator('.bk .name').all_inner_texts(); print('书架:', names)
    pg.locator('.bk', has_text=key).first.click(); pg.wait_for_selector('#text .s', timeout=20000)
    print('章节数:', pg.locator('#btnToc').count(), pg.evaluate('__td.book.chapters.length'), '首章:', pg.evaluate('__td.book.chapters[0].title'))
    pg.screenshot(path=str(OUT / 'r1-book.png'))
    pg.click('#btnToc'); pg.wait_for_selector('#tocList li'); pg.locator('#tocList li').nth(5).click(); time.sleep(1)
    pg.click('#btnPlay'); time.sleep(12)
    st = pg.evaluate("({ch:__td.ch,si:__td.si,t:document.querySelector('#audio').currentTime,d:document.querySelector('#audio').duration,paused:document.querySelector('#audio').paused,title:document.querySelector('#rChap').innerText,mode:__td.mode})")
    print(st); pg.screenshot(path=str(OUT / 'r2-play.png'))
    ok = st['mode'] == 'audio' and st['t'] > 6 and not st['paused'] and not errs
    print('REMOTE', 'PASS' if ok else 'FAIL', errs[:2]); b.close(); sys.exit(0 if ok else 1)
