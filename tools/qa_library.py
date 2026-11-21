#!/usr/bin/env python3
"""书库体检（数据层）：python3 tools/qa_library.py <库目录> [--url <公网书库地址>] [--strict]
检查：index/book.json 结构、章节与句子、时间轴单调、mp3 实际时长 vs 时间轴、语速合理性、文本乱码/广告残留、体积；
--url 另外做 HTTP 体检（index.json 可达、mp3 Range=206、CORS 头、从外网视角抓取）。
退出码 0=全部通过，1=有失败；警告不影响退出码（--strict 时警告也算失败）。
"""
import argparse, json, re, sys, urllib.request
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('lib'); ap.add_argument('--url'); ap.add_argument('--strict', action='store_true')
    a = ap.parse_args(); lib = Path(a.lib)
    from mutagen.mp3 import MP3
    fails, warns = [], []
    F = lambda m: fails.append(m); W = lambda m: warns.append(m)
    idx = json.load(open(lib / 'index.json', encoding='utf-8'))
    ids = [b['id'] for b in idx]
    if len(ids) != len(set(ids)): F('index.json 有重复 id')
    tot_bytes = tot_dur = tot_chars = 0
    rows = []
    for b in idx:
        bid = b['id']; bp = lib / bid / 'book.json'
        if not bp.exists(): F(f'{bid}: 缺 book.json'); continue
        bk = json.load(open(bp, encoding='utf-8')); chs = bk['chapters']
        if not chs: F(f'{bid}: 0 章'); continue
        if b['chapters'] != len(chs): F(f'{bid}: index 章数 {b["chapters"]} != 实际 {len(chs)}')
        chars = dur = audio_n = 0; bad_text = 0; ads = 0; maxch = 0
        for i, c in enumerate(chs, 1):
            sents = [s for p in c['paras'] for s in p]; txt = ''.join(sents)
            if not sents: F(f'{bid} 第{i}章「{c["title"][:12]}」无句子'); continue
            chars += len(txt); maxch = max(maxch, len(txt))
            cjk = len(re.findall(r'[\u4e00-\u9fff]', txt))
            if '\ufffd' in txt or (len(txt) > 50 and cjk / len(txt) < 0.5): bad_text += 1
            if re.search(r'(ireadweek|z-?library|更多.{0,4}电子书|https?://)', txt, re.I): ads += 1
            if c.get('audio'):
                audio_n += 1; t = c['times']; mp = lib / bid / c['audio']
                if len(t) != len(sents): F(f'{bid} 第{i}章 times({len(t)})≠句子({len(sents)})'); continue
                if any(t[k] >= t[k + 1] for k in range(len(t) - 1)): F(f'{bid} 第{i}章 时间轴不单调')
                if not mp.exists(): F(f'{bid} 第{i}章 缺音频 {c["audio"]}'); continue
                real = MP3(str(mp)).info.length; tot_bytes += mp.stat().st_size; dur += real
                if t and t[-1] / 1000 > real + 0.5: F(f'{bid} 第{i}章 最后一句起点 {t[-1]/1000:.1f}s > 音频时长 {real:.1f}s')
                cps = len(txt) / real if real else 0
                if not (2.0 <= cps <= 9.0): W(f'{bid} 第{i}章 语速异常 {cps:.1f} 字/秒（{len(txt)}字/{real:.0f}s）')
        if audio_n != len(chs): F(f'{bid}: 仅 {audio_n}/{len(chs)} 章有音频')
        if bad_text: F(f'{bid}: {bad_text} 章疑似乱码')
        if ads: W(f'{bid}: {ads} 章疑似含广告/链接残留')
        if maxch > 15000: W(f'{bid}: 最长章 {maxch} 字，偏长')
        tot_chars += chars; tot_dur += dur; rows.append((bid, b['title'], len(chs), chars, dur))
    print(f'{"id":16}{"书名":22}{"章":>5}{"字数":>9}{"时长":>9}')
    for r in rows: print(f'{r[0]:16}{r[1][:11]:22}{r[2]:>5}{r[3]:>9}{r[4]/3600:>8.2f}h')
    print(f'合计 {len(rows)} 本 / {tot_chars} 字 / {tot_dur/3600:.1f} 小时 / 音频 {tot_bytes/1e6:.0f} MB')
    if a.url:
        base = a.url.rstrip('/') + '/'
        def get(u, hdr=None, method='GET'):
            req = urllib.request.Request(u, headers=hdr or {}, method=method)
            return urllib.request.urlopen(req, timeout=30)
        try:
            r = get(base + 'index.json'); remote = json.loads(r.read())
            if [x['id'] for x in remote] != ids: F('远程 index.json 与本地不一致')
            if r.headers.get('access-control-allow-origin') != '*': F('缺 CORS 头')
            b0 = idx[0]; bk = json.load(open(lib / b0['id'] / 'book.json', encoding='utf-8'))
            au = next((c['audio'] for c in bk['chapters'] if c.get('audio')), None)
            if au:
                r = get(f'{base}{b0["id"]}/{au}', {'Range': 'bytes=100-199'})
                if r.status != 206 or len(r.read()) != 100: F('音频 Range 请求不是 206/100 字节')
            print('HTTP 体检完成')
        except Exception as e: F(f'HTTP 体检失败: {e}')
    for w in warns: print('WARN', w)
    for f in fails: print('FAIL', f)
    ok = not fails and not (a.strict and warns)
    print('QA', 'PASS' if ok else 'FAIL', f'(fail={len(fails)} warn={len(warns)})'); sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
