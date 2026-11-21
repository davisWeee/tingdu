#!/usr/bin/env python3
"""收尾：用 books20.json 的书名/作者/分类/音色回填 book.json 与 index.json（音频不动），按分类+书名排序。
用法: python3 tools/finalize_index.py [库目录，默认 library-private]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
lib = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'library-private')
meta = {b['id']: b for b in json.load(open(ROOT / 'tools/books20.json', encoding='utf-8'))}
meta['lidaxiao3'] = {'title': '李大霄投资战略（第三版）', 'author': '李大霄', 'genre': '投资理财', 'voice': 'zh-CN-YunyangNeural'}
idx = json.load(open(lib / 'index.json', encoding='utf-8')); out = []
ORDER = ['小说', '经典文学', '心理成长', '投资理财', '历史', '历史科普', '国学']
for e in idx:
    m = meta.get(e['id'])
    if m:
        for k in ('title', 'author', 'genre', 'voice'): e[k] = m[k]
        bp = lib / e['id'] / 'book.json'; bk = json.load(open(bp, encoding='utf-8'))
        bk['title'], bk['author'] = m['title'], m['author']; json.dump(bk, open(bp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    out.append(e)
out.sort(key=lambda e: (ORDER.index(e.get('genre')) if e.get('genre') in ORDER else 99, e['title']))
json.dump(out, open(lib / 'index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out), '本:', [f"{e['title'][:6]}" for e in out])
