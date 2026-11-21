#!/usr/bin/env python3
"""扫描版 PDF 的 OCR 结果（ocr_vision.swift 产出的 pNNN.json）+ PDF 书签 -> chapters.json。
用法: python3 tools/extract_ocr.py book.pdf pages_dir out.json --title 书名 --author 作者 [--skip-front 18-24]
思路: 页眉(y>0.88)/页码(y<0.07)丢弃；按每页左边距判定缩进=新段；用书签标题在对应页里模糊匹配定位章节起点。
"""
import argparse, difflib, json, re, sys
from pathlib import Path
import fitz

FIX = [('李大雪', '李大霄'), ('投人', '投入'), ('大宵', '大霄'), ('李大宵', '李大霄'), ('人市', '入市'), ('古全球', '占全球'), ('介入', '介入')]

def norm(s): return re.sub(r'[\s\W_]+', '', s)

def load_lines(pages_dir: Path, pno: int):
    f = pages_dir / f'p{pno:03d}.json'
    L = json.load(open(f, encoding='utf-8')) if f.exists() else []
    body = [l for l in L if 0.07 < l['y'] < 0.88]
    body.sort(key=lambda l: -l['y'])
    longs = [l['x'] for l in body if l['w'] > 0.55]
    left = min(longs) if longs else (min([l['x'] for l in body]) if body else 0.1)
    for l in body: l['page'] = pno; l['left'] = left
    return body

def is_punct_end(t): return bool(re.search(r'[。！？!?”’」』）)；…:：]$', t.strip()))

def build_paras(lines):
    paras, cur = [], ''
    for i, l in enumerate(lines):
        t = l['t'].strip()
        if not t: continue
        indent = l['x'] > l['left'] + 0.03
        short_centered = (l['x'] > l['left'] + 0.08 and l['w'] < 0.6 and not is_punct_end(t))  # 小标题
        if short_centered:
            if cur: paras.append(cur); cur = ''
            paras.append(t); continue
        if indent and cur: paras.append(cur); cur = ''
        cur += t
        # 行很短且以句末标点结束 -> 段落结束
        if l['x'] + l['w'] < l['left'] + 0.72 and is_punct_end(t):
            paras.append(cur); cur = ''
    if cur: paras.append(cur)
    return paras

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf'); ap.add_argument('pages'); ap.add_argument('out')
    ap.add_argument('--title', required=True); ap.add_argument('--author', default='')
    ap.add_argument('--skip', default='18-24', help='跳过的页范围（目录页）')
    ap.add_argument('--first', type=int, default=4); ap.add_argument('--last', type=int, default=257)
    a = ap.parse_args()
    pages = Path(a.pages)
    toc = [(lvl, t.strip(), p) for lvl, t, p in fitz.open(a.pdf).get_toc()]
    # 章节 = 二级条目 + 前言 + 后记（一级的「部分」只当分隔，不单独成章）
    ents = [(t, p, lvl) for lvl, t, p in toc if (lvl == 2 or t in ('前言', '后记'))]
    sk0, sk1 = [int(x) for x in a.skip.split('-')]
    lines = []
    for pno in range(a.first, a.last + 1):
        if sk0 <= pno <= sk1: continue
        lines += load_lines(pages, pno)
    print('lines', len(lines), 'entries', len(ents))
    # 定位标题行
    starts = []  # (entry_idx, line_idx, n_lines_in_title)
    cursor = 0
    for ei, (title, tp, lvl) in enumerate(ents):
        tn = norm(title); best = None
        for li in range(cursor, len(lines)):
            l = lines[li]
            if l['page'] < tp: continue
            if l['page'] > tp + 2 and best is None and ei > 0: break
            for k in (1, 2):
                if li + k > len(lines): continue
                cand = norm(''.join(x['t'] for x in lines[li:li + k]))
                if not cand or abs(len(cand) - len(tn)) > max(3, len(tn) * 0.35): continue
                r = difflib.SequenceMatcher(None, cand, tn).ratio()
                if r >= 0.72 and (best is None or r > best[0]): best = (r, li, k)
                if r >= 0.95: break
            if best and best[0] >= 0.95: break
        if title == '前言' and best is None:
            # 前言 从 first 页起即可
            best = (1.0, 0, 0)
        if best is None:
            print('!! 未定位:', title, tp); continue
        starts.append((ei, best[1], best[2])); cursor = best[1] + max(1, best[2])
    print('located', len(starts), '/', len(ents))
    chapters = []
    for j, (ei, li, k) in enumerate(starts):
        end = starts[j + 1][1] if j + 1 < len(starts) else len(lines)
        seg = lines[li + k:end]
        paras = build_paras(seg)
        txt = []
        for p in paras:
            for x, y in FIX: p = p.replace(x, y)
            p = re.sub(r'\s+', '', p) if not re.search(r'[A-Za-z]{3,}\s[A-Za-z]', p) else re.sub(r'\s{2,}', ' ', p)
            if len(p) >= 2: txt.append(p)
        chapters.append({'title': ents[ei][0], 'paras': txt, 'page': ents[ei][1]})
    json.dump({'title': a.title, 'author': a.author, 'chapters': chapters}, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tot = sum(len(''.join(c['paras'])) for c in chapters)
    print('chapters', len(chapters), 'chars', tot)

if __name__ == '__main__':
    main()
