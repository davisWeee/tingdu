#!/usr/bin/env python3
"""批处理流水线：books20.json 里每本书 下载完成(zip/文本可解析) → extract_book → make_audio（2 本并行）。可反复运行，已完成的跳过。
用法: python3 tools/build_all.py [--lib library-private] [--workers 2] [--conc 16] [--wait]   # --wait: 源文件还没到齐就轮询等待
状态写到 private/build_status.json，便于汇报进度。
"""
import argparse, json, subprocess, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def src_ready(p: Path) -> bool:
    if time.time() - p.stat().st_mtime < 25: return False  # 还在写入
    if p.suffix == '.epub':
        try: zipfile.ZipFile(p).testzip(); return True
        except Exception: return False
    return p.exists() and p.stat().st_size > 1000

def find_src(bid):
    fs = [f for f in (ROOT / 'private/books').glob(bid + '.*') if not f.name.endswith('.part')]
    return fs[0] if fs else None

def do_book(b, lib, conc):
    bid = b['id']; chap = ROOT / f'private/chap/{bid}.json'; log = ROOT / f'private/logs/{bid}.log'; log.parent.mkdir(exist_ok=True, parents=True)
    src = find_src(bid)
    with open(log, 'a') as lg:
        if not chap.exists():
            r = subprocess.run([sys.executable, str(ROOT / 'tools/extract_book.py'), str(src), str(chap), '--title', b['title'], '--author', b['author']], stdout=lg, stderr=lg)
            if r.returncode: return bid, 'extract-failed'
        r = subprocess.run([sys.executable, str(ROOT / 'tools/make_audio.py'), str(chap), '--id', bid, '--out', str(ROOT / lib), '--voice', b['voice'], '--genre', b['genre'], '--conc', str(conc)], stdout=lg, stderr=lg)
        return bid, 'ok' if r.returncode == 0 else 'tts-failed'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--lib', default='library-private'); ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--conc', type=int, default=16); ap.add_argument('--wait', action='store_true'); ap.add_argument('--list', default=str(ROOT / 'tools/books20.json'))
    a = ap.parse_args(); books = json.load(open(a.list, encoding='utf-8'))
    status = {}; done = set()
    idx_path = ROOT / a.lib / 'index.json'
    def finished(bid):
        try: return any(x['id'] == bid and x.get('audio') for x in json.load(open(idx_path, encoding='utf-8')))
        except Exception: return False
    ex = ThreadPoolExecutor(a.workers); futs = {}
    while True:
        for b in books:
            bid = b['id']
            if bid in futs or finished(bid): continue
            s = find_src(bid)
            if s and src_ready(s):
                time.sleep(2)  # 等文件落盘稳定
                if src_ready(s): futs[bid] = ex.submit(do_book, b, a.lib, a.conc); status[bid] = 'running'
        for bid, f in list(futs.items()):
            if f.done() and status.get(bid) == 'running': status[bid] = f.result()[1]; print(bid, status[bid], flush=True)
        json.dump(status, open(ROOT / 'private/build_status.json', 'w'), ensure_ascii=False)
        pending = [b['id'] for b in books if b['id'] not in futs and not finished(b['id'])]
        if not pending and all(f.done() for f in futs.values()): break
        if not a.wait and not any(not f.done() for f in futs.values()) and pending: print('等待源文件:', pending); break
        time.sleep(15)
    print('ALL DONE', status)

if __name__ == '__main__':
    main()
