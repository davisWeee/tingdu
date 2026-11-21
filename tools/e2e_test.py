#!/usr/bin/env python3
"""端到端验收：Chrome for Testing（无头，放开自动播放，手机视口）真点按钮。
用法: python3 tools/e2e_test.py <应用URL> [书库URL|-] [书名关键字]
  - 应用URL 例 http://127.0.0.1:8082/<token>/ 或 https://davisweee.github.io/tingdu/
  - 书库URL 给了就用 ?lib= 连接（私人书库）；书名关键字用来选书（默认书架第一本）
验证：书架/搜索/分类、播放、高亮同步、倍速、点句跳转、暂停、定时、上下章、续读、目录、主题、TXT 导入(朗读模式)、无页面错误；截图存 private/shots。
"""
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8082/'
LIB = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != '-' else None
KEY = sys.argv[3] if len(sys.argv) > 3 else None
CHROME = str(next(Path.home().glob('.hermes/tools/chromium-*/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing')))
OUT = Path(__file__).resolve().parent.parent / 'private' / 'shots'; OUT.mkdir(parents=True, exist_ok=True)
ok = True
def check(name, cond, extra=''):
    global ok; ok &= bool(cond); print(('PASS ' if cond else 'FAIL ') + name, str(extra)[:160], flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True, args=['--autoplay-policy=no-user-gesture-required', '--no-sandbox'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page(); logs = []
    pg.on('console', lambda m: logs.append(m.text)); pg.on('pageerror', lambda e: logs.append('PAGEERR ' + str(e)))
    pg.goto(URL + (f'?lib={LIB}' if LIB else '')); pg.wait_for_selector('.bk', timeout=20000); time.sleep(1)
    pg.screenshot(path=str(OUT / '1-shelf.png'))
    n = pg.locator('.bk').count(); check('书架有书', n >= 1, f'{n} 本')
    first = pg.locator('.bk .name').first.inner_text()
    pg.fill('#q', first[:2]); time.sleep(0.4); check('搜索过滤', 1 <= pg.locator('.bk').count() <= n)
    pg.fill('#q', '不存在的书名xyz'); time.sleep(0.4); check('搜索无结果提示', pg.locator('.bk').count() == 0 and '没有匹配' in pg.inner_text('#shelfHint'))
    pg.fill('#q', ''); time.sleep(0.4)
    if pg.locator('#chips button').count() > 2:
        pg.locator('#chips button').nth(1).click(); time.sleep(0.3); c1 = pg.locator('.bk').count(); pg.locator('#chips button').nth(0).click(); time.sleep(0.3)
        check('分类筛选', 1 <= c1 <= n and pg.locator('.bk').count() == n, f'{c1}/{n}')
    (pg.locator('.bk', has_text=KEY).first if KEY else pg.locator('.bk').first).click(); pg.wait_for_selector('#text .s')
    st = lambda: pg.evaluate("({si:__td.si,mode:__td.mode,playing:__td.playing,t:document.querySelector('#audio').currentTime,d:document.querySelector('#audio').duration,paused:document.querySelector('#audio').paused,ch:__td.ch,n:__td.flat.length,chs:__td.book.chapters.length,speed:__td.speed})")
    s0 = st(); check('进入阅读 audio 模式', s0['mode'] == 'audio', s0)
    pg.click('#btnPlay'); time.sleep(14)
    s1 = st(); check('播放中且时间前进', s1['playing'] and s1['t'] > 8 and not s1['paused'], s1)
    check('高亮随播放推进', s1['si'] > 0, f"si={s1['si']}")
    check('高亮句与时间匹配', pg.evaluate("(()=>{const t=__td.times,ms=document.querySelector('#audio').currentTime*1000;const i=__td.si;return t[i]<=ms+300&&(i+1>=t.length||t[i+1]>ms-300)})()"))
    pg.screenshot(path=str(OUT / '2-playing.png'))
    pg.click('#btnSpeed'); pg.locator('#speedList button', has_text='1.5x').click(); time.sleep(1)
    check('倍速 1.5x 生效', abs(pg.evaluate("document.querySelector('#audio').playbackRate") - 1.5) < 0.01 and '1.5x' in pg.inner_text('#btnSpeed'))
    tgt = min(10, s1['n'] - 1)
    pg.locator('#text .s').nth(tgt).click(); time.sleep(1.2)
    s2 = st(); check(f'点第 {tgt + 1} 句跳转并继续播放', s2['si'] >= tgt and s2['playing'], s2)
    pg.click('#btnSleep'); pg.locator('#sleepList button', has_text='本章结束').click(); time.sleep(0.3)
    check('定时=本章结束', pg.evaluate('__td.sleepEnd') is True)
    pg.click('#btnSleep'); pg.locator('#sleepList button', has_text='关闭').click()
    pg.click('#btnPlay'); time.sleep(0.5); t3 = st()['t']; time.sleep(1.2)
    check('暂停有效', st()['t'] - t3 < 0.05)
    pg.click('#btnNext'); time.sleep(1.5); s4 = st(); check('下一章', s4['ch'] == 1 and s4['mode'] == 'audio', s4)
    pg.click('#btnPrev'); time.sleep(1); check('上一章', st()['ch'] == 0)
    pg.click('#btnNext'); time.sleep(1)
    pg.reload(); pg.wait_for_selector('.bk'); time.sleep(1.5); check('书架有继续阅读卡', pg.locator('#continue .cont').count() == 1)
    pg.click('#continue .cont'); pg.wait_for_selector('#text .s'); time.sleep(1.5)
    check('续读回到第 2 章', pg.evaluate('__td.ch') == 1)
    pg.click('#btnToc'); pg.wait_for_selector('#tocList li'); pg.screenshot(path=str(OUT / '4-toc.png'))
    check('目录条数=章数', pg.locator('#tocList li').count() == st()['chs'])
    pg.click('#sheetMask', position={'x': 10, 'y': 10})
    pg.click('#btnSet'); pg.locator('#segTheme button[data-v=night]').click(); pg.screenshot(path=str(OUT / '5-night.png'))
    check('夜间主题', pg.evaluate("document.body.dataset.theme") == 'night'); pg.locator('#segTheme button[data-v=paper]').click()
    pg.click('#sheetMask', position={'x': 10, 'y': 10}); pg.click('#btnBack'); pg.wait_for_selector('#books'); time.sleep(0.5)
    txt = ('第一章 开始\n' + '这是测试文本。' * 40 + '\n第二章 继续\n' + '再来一段内容，用来验证导入。' * 40).encode('utf-8')
    pg.set_input_files('#fileInput', files=[{'name': '测试导入.txt', 'mimeType': 'text/plain', 'buffer': txt}]); time.sleep(1.2)
    check('TXT 导入后上架', pg.locator('.bk', has_text='测试导入').count() == 1)
    pg.locator('.bk', has_text='测试导入').click(); pg.wait_for_selector('#text .s')
    check('导入书走手机朗读模式', pg.evaluate('__td.mode') == 'tts' and pg.evaluate('__td.book.chapters.length') == 2, pg.inner_text('#modeTag'))
    errs = [l for l in logs if 'PAGEERR' in l or 'Uncaught' in l]; check('无页面错误', not errs, errs[:2])
    b.close()
print('ALL PASS' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
