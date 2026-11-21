#!/usr/bin/env python3
"""EPUB / TXT -> chapters.json（给 make_audio.py 用）。
用法: python3 tools/extract_book.py <文件> <out.json> --title 书名 --author 作者
EPUB: 按 spine 顺序取每个 xhtml；章节名取目录(nav/ncx)里对应项，其次 h1-h3，其次首行；过短的前后页(封面/版权/广告)丢弃；超长章节按段落切成 上/中/下。
TXT : UTF-8/GB18030 自动识别，按「第X章/回/节」切章，没有章标记则按约 3000 字切。
"""
import argparse, json, posixpath, re, sys, zipfile
from pathlib import Path
from lxml import etree, html as lhtml

AD = re.compile(r'(更多(免费)?(电子书|书籍|好书)|下载.{0,6}(电子书|书籍)|ireadweek|zlibrary|z-library|公众号|微信号|关注.{0,6}(微信|公众号)|扫.{0,4}二维码|本书由.{0,10}(整理|制作)|www\.|https?://|1lib|mrbook)', re.I)
BOILER = re.compile(r'^(图书在版编目|CIP\s*数据|ISBN|版权所有|出版发行|责任编辑|责任校对|版次|印次|定价|书名原文|Copyright|All rights reserved|THE\s+[A-Z ]+by\s)', re.I)
REFS = re.compile(r'^(尾注|注释|参考书目|参考数据|参考文献|索引|附注|地图\d*|图片来源|版权声明)')
SKIP_TITLE = re.compile(r'^(封面|封底|版权|版权页|书名页|扉页|目录|目\s*录|出版说明|插图|图片|广告|版权信息|献词|赞誉|推荐语|编辑推荐|作者简介|关于作者|书籍信息|制作说明|版本说明|table\s+of\s+contents|cover|toc|contents|copyright|title\s*page)$', re.I)
CH_RE = re.compile(r'^\s*(第[零〇一二三四五六七八九十百千两\d]+[章节回篇卷部集]|Chapter\s+\d+|序章|序言|序|前言|引言|后记|尾声|楔子|终章|结语|致谢)(?=$|[\s：:、.．—-])', re.I)
MAXCH = 9000

def clean_para(p: str) -> str:
    p = re.sub(r'[\u200b\u200c\u200d\ufeff\u00a0]', '', p).replace('\u3000', ' ')
    p = re.sub(r'\s+', ' ', p).strip()
    if re.search(r'[\u4e00-\u9fff]', p): p = re.sub(r'(?<=[\u4e00-\u9fff，。！？、；：“”‘’（）《》—…]) (?=[\u4e00-\u9fff，。！？、；：“”‘’（）《》—…])', '', p)
    return p

def html_to_paras(raw: bytes):
    try: root = lhtml.fromstring(raw)
    except Exception: return None, []
    for bad in root.xpath('//script|//style|//svg|//img|//sup[contains(@class,"note")]|//rt|//rp'): bad.getparent().remove(bad)
    title = None
    for h in root.xpath('//h1|//h2|//h3'):
        t = clean_para(h.text_content())
        if t: title = t; break
    paras = []
    blocks = root.xpath('//body//p|//body//h1|//body//h2|//body//h3|//body//h4|//body//li|//body/div[not(.//p)]|//body//blockquote[not(.//p)]')
    if not blocks: blocks = [root.xpath('//body')[0]] if root.xpath('//body') else []
    for el in blocks:
        txt = el.text_content()
        for part in re.split(r'\n\s*\n', txt):
            p = clean_para(part)
            if p: paras.append(p)
    # 去掉相邻重复（div 嵌套造成）
    out = []
    for p in paras:
        if out and out[-1] == p: continue
        out.append(p)
    return title, out

def epub_chapters(path: Path):
    z = zipfile.ZipFile(path)
    cont = etree.fromstring(z.read('META-INF/container.xml'))
    opf_path = cont.xpath('//*[local-name()="rootfile"]/@full-path')[0]
    opf = etree.fromstring(z.read(opf_path)); base = posixpath.dirname(opf_path)
    man = {i.get('id'): (i.get('href'), i.get('media-type'), i.get('properties') or '') for i in opf.xpath('//*[local-name()="manifest"]/*[local-name()="item"]')}
    spine = [man[r.get('idref')] for r in opf.xpath('//*[local-name()="spine"]/*[local-name()="itemref"]') if r.get('idref') in man]
    # 目录标题映射 href(无锚点)->title
    toc = {}
    def add(href, t):
        href = posixpath.normpath(posixpath.join(base, href.split('#')[0]))
        if href not in toc and t.strip(): toc[href] = clean_para(t)
    for iid, (href, mt, props) in man.items():
        try:
            if 'nav' in props.split():
                nav = lhtml.fromstring(z.read(posixpath.normpath(posixpath.join(base, href))))
                for a in nav.xpath('//nav//a'):
                    if a.get('href'): add(posixpath.join(posixpath.dirname(href), a.get('href')), a.text_content())
            elif mt == 'application/x-dtbncx+xml':
                ncx = etree.fromstring(z.read(posixpath.normpath(posixpath.join(base, href))))
                for np_ in ncx.xpath('//*[local-name()="navPoint"]'):
                    t = ''.join(np_.xpath('./*[local-name()="navLabel"]//text()')); c = np_.xpath('./*[local-name()="content"]/@src')
                    if c: add(posixpath.join(posixpath.dirname(href), c[0]), t)
        except Exception: pass
    chapters = []
    for href, mt, _ in spine:
        if 'html' not in (mt or ''): continue
        full = posixpath.normpath(posixpath.join(base, href))
        try: raw = z.read(full)
        except KeyError: continue
        h_title, paras = html_to_paras(raw)
        title = toc.get(full) or h_title or ''
        if paras and h_title and paras[0] == h_title: paras = paras[1:]
        if paras and toc.get(full) and paras[0] == toc[full]: paras = paras[1:]
        chapters.append({'title': title, 'paras': paras})
    return chapters

def mobi_chapters(path: Path):
    import mobi, shutil
    tmp, fp = mobi.extract(str(path)); fp = Path(fp)
    try:
        if fp.suffix.lower() == '.epub': return epub_chapters(fp)
        if fp.suffix.lower() in ('.html', '.htm'):
            _, paras = html_to_paras(fp.read_bytes()); chs, cur = [], {'title': '', 'paras': []}
            for p_ in paras:
                if len(p_) < 40 and CH_RE.match(p_):
                    if cur['paras']: chs.append(cur)
                    cur = {'title': p_, 'paras': []}
                else: cur['paras'].append(p_)
            if cur['paras']: chs.append(cur)
            return chs
        raise RuntimeError(f'不支持的 mobi 解包结果: {fp}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def decode_text(b: bytes) -> str:
    for enc in ('utf-8-sig', 'gb18030'):
        try: return b.decode(enc)
        except Exception: pass
    return b.decode('utf-8', 'ignore')

def txt_chapters(path: Path):
    lines = decode_text(path.read_bytes()).replace('\r', '').split('\n')
    chs, cur = [], {'title': '开篇', 'paras': []}
    for ln in lines:
        s = ln.strip()
        if s and len(s) < 40 and CH_RE.match(s):
            if cur['paras']: chs.append(cur)
            cur = {'title': clean_para(s), 'paras': []}
        elif s: cur['paras'].append(clean_para(s))
    if cur['paras']: chs.append(cur)
    if len(chs) <= 2:
        paras = [clean_para(l) for l in lines if l.strip()]; chs = []; acc, n = [], 0
        for p in paras:
            acc.append(p); n += len(p)
            if n > 3000: chs.append({'title': f'第 {len(chs) + 1} 部分', 'paras': acc}); acc, n = [], 0
        if acc: chs.append({'title': f'第 {len(chs) + 1} 部分', 'paras': acc})
    return chs

def finalize(chs, book_title):
    out = []
    for c in chs:
        paras = [p for p in c['paras'] if '\ufffd' not in p and not BOILER.search(p) and not AD.search(p) and not re.fullmatch(r'[\d\s·\-—.]+', p) and len(p) > 1]
        title = (c['title'] or '').strip()
        n = sum(len(p) for p in paras)
        txt_ = ''.join(paras); cjk_ = len(re.findall(r'[\u4e00-\u9fff]', txt_)) / max(1, len(txt_))
        if (n < 1500 and re.search(r'CIP数据核字|ISBN|版权所有|未经出版者书面许可|出版发行|印数|责任印制', txt_)) or REFS.match(title) or (n > 200 and cjk_ < 0.3) or (n < 2500 and cjk_ < 0.5 and re.match(r'^(目录|目\s*录|总目录)', txt_)):
            continue  # 尾注/参考书目/外文原版/目录页
        if SKIP_TITLE.match(title) or n < 120: 
            if n >= 120 and not SKIP_TITLE.match(title): pass
            else: continue
        out.append({'title': title, 'paras': paras})
    # 超长章节：先按内部「第X章」类标题行切；没有就按段落均分
    final = []
    for c in out:
        n = sum(len(p) for p in c['paras'])
        if n <= MAXCH * 1.3: final.append(c); continue
        marks = [i for i, p in enumerate(c['paras']) if len(p) < 40 and CH_RE.match(p)]
        if len(marks) >= 3:
            bounds = marks + [len(c['paras'])]
            if marks[0] > 0 and sum(len(p) for p in c['paras'][:marks[0]]) > 200: final.append({'title': c['title'], 'paras': c['paras'][:marks[0]]})
            for a_, b_ in zip(bounds, bounds[1:]):
                final.append({'title': c['paras'][a_], 'paras': c['paras'][a_ + 1:b_]})
            continue
        k = round(n / MAXCH); target = n / k; parts, acc, m = [], [], 0
        for p in c['paras']:
            acc.append(p); m += len(p)
            if m >= target and len(parts) < k - 1: parts.append(acc); acc, m = [], 0
        if acc: parts.append(acc)
        short = len(c['title']) <= 12
        for i, pa in enumerate(parts, 1):
            final.append({'title': f"{c['title']}（{i}/{len(parts)}）" if short else f"第 {i} 部分", 'paras': pa})
    # 规范标题：空标题/纯数字(含罗马数字)标题 → 「第N章」，N 为原章序；拆分的章带 (i/n)
    seq = 0; part = 0; res = []
    for c in final:
        ti = c['title']; m = re.fullmatch(r'(.*?)（(\d+)/(\d+)）', ti)
        base, suf = (m.group(1), f'（{m.group(2)}/{m.group(3)}）') if m else (ti, '')
        if not base:
            part += 1; res.append({'title': f'第{part}部分', 'paras': c['paras']}); continue
        if re.fullmatch(r'[\d\s·.\-—IVXLCivxlc]+', base):
            if not (m and int(m.group(2)) > 1): seq += 1
            base = f'第{seq}章'
        elif not m or int(m.group(2)) == 1: seq += 1
        res.append({'title': base + suf, 'paras': c['paras']})
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--title', required=True); ap.add_argument('--author', default='')
    a = ap.parse_args(); src = Path(a.src)
    ext = src.suffix.lower()
    chs = epub_chapters(src) if ext == '.epub' else mobi_chapters(src) if ext in ('.mobi', '.azw3', '.azw') else txt_chapters(src)
    chs = finalize(chs, a.title)
    json.dump({'title': a.title, 'author': a.author, 'chapters': chs}, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tot = sum(len(''.join(c['paras'])) for c in chs)
    print(f'{src.name}: {len(chs)} 章, {tot} 字' + ('  ⚠无章节' if not chs else ''))

if __name__ == '__main__':
    main()
