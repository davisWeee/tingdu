#!/usr/bin/env python3
"""章节 JSON -> 有声书库（book.json + 每章 mp3，句级时间轴）。

输入  chapters.json: {"title","author","chapters":[{"title","paras":["整段文字",..]}]}
输出  <out>/<id>/book.json, <out>/<id>/chNN.mp3, 并登记到 <out>/index.json

用法: python3 tools/make_audio.py chapters.json --id lidaxiao3 --out library-private
      [--voice zh-CN-XiaoxiaoNeural] [--rate +0%] [--only 1,2] [--no-audio]
特点: 句子级合成 + 本地缓存(可断点续跑) + ffmpeg 无损拼接 + mutagen 取每句时长做高亮时间轴。
"""
import argparse, asyncio, hashlib, json, os, re, subprocess, sys
from pathlib import Path

FFMPEG = os.environ.get('FFMPEG', str(Path.home() / '.hermes/tools/ffmpeg-9.0.1-darwin-x64/ffmpeg'))
END = re.compile(r'([。！？!?；;…]+[”’」』）)]*)')

def split_sentences(text: str):
    parts = [p for p in END.split(text) if p]
    out, buf = [], ''
    for p in parts:
        buf += p
        if END.fullmatch(p):
            out.append(buf); buf = ''
    if buf.strip(): out.append(buf)
    # 合并过短句；拆分过长句（便于 TTS 稳定、高亮粒度合适）
    merged = []
    for s in out:
        s = s.strip()
        if not s: continue
        if merged and len(merged[-1]) < 12: merged[-1] += s
        else: merged.append(s)
    final = []
    for s in merged:
        while len(s) > 90:
            cut = max(s.rfind('，', 0, 80), s.rfind('、', 0, 80), s.rfind(',', 0, 80))
            if cut < 30: cut = 80
            final.append(s[:cut + 1]); s = s[cut + 1:]
        final.append(s)
    return final

async def synth_all(jobs, voice, rate, cache: Path, conc=8):
    import edge_tts
    sem = asyncio.Semaphore(conc)
    done = 0
    total = len(jobs)
    async def one(text):
        nonlocal done
        key = hashlib.sha1(f'{voice}|{rate}|{text}'.encode()).hexdigest()
        f = cache / f'{key}.mp3'
        if f.exists() and f.stat().st_size > 200:
            return f
        async with sem:
            for attempt in range(6):
                try:
                    await edge_tts.Communicate(text, voice, rate=rate).save(str(f))
                    if f.stat().st_size > 200: break
                except Exception as e:
                    await asyncio.sleep(1.5 * (attempt + 1))
            else:
                raise RuntimeError(f'TTS failed: {text[:30]}')
        done += 1
        if done % 100 == 0: print(f'  tts {done}/{total}', flush=True)
        return f
    return await asyncio.gather(*[one(t) for t in jobs])

def mp3_len(path) -> float:
    from mutagen.mp3 import MP3
    return MP3(str(path)).info.length

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chapters'); ap.add_argument('--id', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--voice', default='zh-CN-XiaoxiaoNeural'); ap.add_argument('--rate', default='+0%')
    ap.add_argument('--only', default=''); ap.add_argument('--no-audio', action='store_true')
    ap.add_argument('--conc', type=int, default=8); ap.add_argument('--genre', default='')
    a = ap.parse_args()
    src = json.load(open(a.chapters, encoding='utf-8'))
    out = Path(a.out) / a.id; out.mkdir(parents=True, exist_ok=True)
    cache = Path(a.out) / '.tts_cache'; cache.mkdir(parents=True, exist_ok=True)
    only = {int(x) for x in a.only.split(',') if x}
    book = {'id': a.id, 'title': src['title'], 'author': src.get('author', ''), 'voice': a.voice, 'chapters': []}
    for ci, ch in enumerate(src['chapters'], 1):
        paras = [split_sentences(p) for p in ch['paras'] if p.strip()]
        paras = [p for p in paras if p]
        entry = {'title': ch['title'], 'paras': paras}
        sents = [s for p in paras for s in p]
        if not a.no_audio and sents and (not only or ci in only):
            files = asyncio.run(synth_all(sents, a.voice, a.rate, cache, a.conc))
            lens = [mp3_len(f) for f in files]
            times, t = [], 0.0
            for L in lens: times.append(int(t * 1000)); t += L
            lst = out / f'.ch{ci:02d}.txt'
            lst.write_text(''.join(f"file '{Path(f).resolve()}'\n" for f in files))
            mp3 = out / f'ch{ci:02d}.mp3'
            subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(mp3)], check=True)
            lst.unlink()
            real = mp3_len(mp3)
            entry['audio'] = mp3.name; entry['times'] = times; entry['dur'] = round(real, 1)
            print(f'[{ci}/{len(src["chapters"])}] {ch["title"][:20]} 句{len(sents)} 时长{real:.0f}s (累计偏差{real - t:+.1f}s)', flush=True)
        else:
            old = out / 'book.json'
            if old.exists():  # --only 时保留旧章节音频信息
                try:
                    o = json.load(open(old, encoding='utf-8'))['chapters'][ci - 1]
                    if o.get('audio') and o['paras'] == paras: entry.update({k: o[k] for k in ('audio', 'times', 'dur') if k in o})
                except Exception: pass
        book['chapters'].append(entry)
        json.dump(book, open(out / 'book.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    # 登记 index.json
    idx_path = Path(a.out) / 'index.json'
    idx = json.load(open(idx_path, encoding='utf-8')) if idx_path.exists() else []
    idx = [b for b in idx if b['id'] != a.id]
    chars = sum(len(s) for c in book['chapters'] for p in c['paras'] for s in p)
    hours = round(sum(c.get('dur', 0) for c in book['chapters']) / 3600, 1)
    idx.append({'id': a.id, 'title': book['title'], 'author': book['author'], 'genre': a.genre, 'chapters': len(book['chapters']),
                'chars': chars, 'hours': hours, 'voice': a.voice, 'audio': all('audio' in c for c in book['chapters'])})
    json.dump(idx, open(idx_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('done', out)

if __name__ == '__main__':
    main()
