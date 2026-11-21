#!/usr/bin/env python3
"""端到端验收：本地静态服务 + Chrome for Testing（无头，放开自动播放），真点按钮，验证 播放/高亮同步/倍速/跳句/下一章/续读，并截手机尺寸图。
用法: python3 tools/e2e_test.py [http://127.0.0.1:8081/] [书ID，默认 demo]
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8081/'
CHROME = str(next(Path.home().glob('.hermes/tools/chromium-*/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing')))
OUT = Path(__file__).resolve().parent.parent / 'private' / 'shots'; OUT.mkdir(parents=True, exist_ok=True)
ok = True
def check(name, cond, extra=''):
    global ok; ok &= bool(cond); print(('PASS ' if cond else 'FAIL ') + name, extra, flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True, args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page(); logs = []
    pg.on('console', lambda m: logs.append(m.text)); pg.on('pageerror', lambda e: logs.append('PAGEERR ' + str(e)))
    pg.goto(URL); pg.wait_for_selector('.bk'); pg.screenshot(path=str(OUT / '1-shelf.png'))
    check('书架有书', pg.locator('.bk').count() >= 1)
    pg.locator('.bk').first.click(); pg.wait_for_selector('#text .s')
    st = lambda: pg.evaluate("({si:__td.si,mode:__td.mode,playing:__td.playing,t:document.querySelector('#audio').currentTime,d:document.querySelector('#audio').duration,paused:document.querySelector('#audio').paused,ch:__td.ch,n:__td.flat.length,speed:__td.speed})")
    s0 = st(); check('进入阅读 audio 模式', s0['mode'] == 'audio', s0)
    pg.click('#btnPlay'); time.sleep(14)
    s1 = st(); check('播放中且时间前进', s1['playing'] and s1['t'] > 8 and not s1['paused'], s1)
    check('高亮随播放推进', s1['si'] > 0, f"si={s1['si']}")
    on = pg.evaluate("document.querySelector('.s.on').innerText")
    check('高亮句与时间匹配', pg.evaluate("(()=>{const t=__td.times,ms=document.querySelector('#audio').currentTime*1000;const i=__td.si;return t[i]<=ms+300&&(i+1>=t.length||t[i+1]>ms-300)})()"), on[:12])
    pg.screenshot(path=str(OUT / '2-playing.png'))
    # 倍速
    pg.click('#btnSpeed'); pg.locator('#speedList button', has_text='1.5x').click(); time.sleep(1)
    check('倍速 1.5x 生效', abs(pg.evaluate("document.querySelector('#audio').playbackRate") - 1.5) < 0.01)
    pg.screenshot(path=str(OUT / '3-speed.png'))
    # 点句跳转
    pg.locator('#text .s').nth(10).click(); time.sleep(1.2)
    s2 = st(); check('点第 11 句跳转并继续播放', s2['si'] >= 10 and s2['playing'], s2)
    # 暂停
    pg.click('#btnPlay'); time.sleep(0.5); s3 = st(); t3 = s3['t']; time.sleep(1.2)
    check('暂停有效', st()['t'] - t3 < 0.05)
    # 下一章
    pg.click('#btnNext'); time.sleep(1.5); s4 = st(); check('下一章', s4['ch'] == 1 and s4['mode'] == 'audio', s4)
    # 续读：重新加载页面，书架出现「继续」
    pg.reload(); pg.wait_for_selector('.bk'); check('书架有继续阅读卡', pg.locator('#continue .cont').count() == 1)
    pg.click('#continue .cont'); pg.wait_for_selector('#text .s'); time.sleep(1.5)
    check('续读回到第 2 章', pg.evaluate('__td.ch') == 1)
    # 目录/设置抽屉
    pg.click('#btnToc'); pg.wait_for_selector('#tocList li'); pg.screenshot(path=str(OUT / '4-toc.png')); pg.click('#sheetMask', position={'x': 10, 'y': 10})
    pg.click('#btnSet'); pg.locator('#segTheme button[data-v=night]').click(); pg.screenshot(path=str(OUT / '5-night.png'))
    errs = [l for l in logs if 'PAGEERR' in l or 'Uncaught' in l]; check('无页面错误', not errs, errs[:2])
    b.close()
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
