/* 听读 — 边看边听。纯静态 PWA，无依赖。
 * 书库格式: <base>/index.json = [{id,title,author,chapters,audio}]
 *           <base>/<id>/book.json = {title,author,chapters:[{title,paras:[[句,句],..],audio?,times?:[每句起始毫秒]}]}
 * 章节有 audio → 用 <audio> 播放并按 times 高亮；否则用浏览器朗读(speechSynthesis)。
 */
(() => {
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { toast('存储空间不足'); } },
};
const SPEEDS = [0.8, 1, 1.25, 1.5, 1.75, 2, 2.5];
const SLEEPS = [['关闭', 0], ['15 分钟', 15], ['30 分钟', 30], ['60 分钟', 60], ['本章结束', -1]];

const S = {
  libs: [], books: [], book: null, bookMeta: null, ch: 0, si: 0,
  flat: [],            // 当前章扁平句子 [{el,text}]
  times: null,         // 当前章每句起始毫秒（有音频时）
  mode: 'tts',         // 'audio' | 'tts'
  playing: false, speed: LS.get('td.speed', 1),
  set: Object.assign({ theme: 'paper', fs: 19, lh: 1.95, follow: 1, voice: '' }, LS.get('td.set', {})),
  sleepAt: 0, sleepEnd: false, ttsToken: 0, ttsStart: 0,
};
const audio = $('#audio');

/* ---------------- 工具 ---------------- */
function toast(msg, ms = 2200) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), ms);
}
const fmt = s => { s = Math.max(0, Math.round(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };
function hue(str) { let h = 0; for (const c of str) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
function coverStyle(title) { const h = hue(title); return `background:linear-gradient(155deg,hsl(${h} 45% 38%),hsl(${(h + 40) % 360} 50% 26%))`; }
const joinUrl = (base, p) => base.replace(/\/?$/, '/') + p;
function esc(s) { return s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

/* ---------------- 书库 ---------------- */
function initLibs() {
  const u = new URL(location.href);
  const add = u.searchParams.get('lib');
  let libs = LS.get('td.libs', []);
  if (add) {
    if (!libs.includes(add)) libs.push(add);
    LS.set('td.libs', libs);
    u.searchParams.delete('lib'); history.replaceState(null, '', u.pathname + u.search + u.hash);
    toast('已连接私人书库');
  }
  S.libs = ['./library/', ...libs];
}
async function loadBooks() {
  const out = [];
  for (const base of S.libs) {
    try {
      const r = await fetch(joinUrl(base, 'index.json'), { cache: 'no-cache' });
      if (!r.ok) continue;
      for (const b of await r.json()) out.push({ ...b, base, key: base + '|' + b.id });
    } catch (e) { /* 书库不可达就跳过 */ }
  }
  for (const b of LS.get('td.local', [])) out.push({ id: b.id, title: b.title, author: '本地导入', chapters: b.chapters.length, audio: false, local: true, key: 'local|' + b.id });
  S.books = out;
  renderShelf();
}
function progOf(key) { return LS.get('td.prog', {})[key]; }
function saveProg() {
  if (!S.bookMeta) return;
  const p = LS.get('td.prog', {});
  p[S.bookMeta.key] = { ch: S.ch, si: S.si, t: Date.now() };
  LS.set('td.prog', p);
}
function renderShelf() {
  const box = $('#books'); box.innerHTML = '';
  S.books.forEach(b => {
    const p = progOf(b.key);
    const d = document.createElement('div'); d.className = 'bk';
    d.innerHTML = `<div class="cv" style="${coverStyle(b.title)}">${b.audio ? '<span class="badge">🎧 有声</span>' : ''}
      <div class="t">${esc(b.title)}</div><div class="a">${esc(b.author || '')}</div></div>
      <div class="name">${esc(b.title)}</div><div class="pg">${p ? `读到 第${p.ch + 1}章` : `${b.chapters} 章`}</div>`;
    d.onclick = () => openBook(b);
    if (b.local) { let tm; d.oncontextmenu = e => { e.preventDefault(); delLocal(b); }; d.ontouchstart = () => (tm = setTimeout(() => delLocal(b), 700)); d.ontouchend = () => clearTimeout(tm); }
    box.appendChild(d);
  });
  $('#shelfHint').textContent = S.books.length ? '' : '书架是空的：点右上角导入 TXT，或「连接私人书库」。';
  // 继续阅读
  const last = S.books.filter(b => progOf(b.key)).sort((a, b) => progOf(b.key).t - progOf(a.key).t)[0];
  const c = $('#continue');
  if (last) {
    const p = progOf(last.key);
    c.hidden = false;
    c.innerHTML = `<div class="cont"><div class="cv" style="${coverStyle(last.title)};aspect-ratio:auto"><div class="t" style="font-size:11px;-webkit-line-clamp:3">${esc(last.title)}</div></div>
      <div class="meta"><b>${esc(last.title)}</b><span>上次读到 第${p.ch + 1}章 · 继续听</span></div><button class="go">继续</button></div>`;
    c.firstElementChild.onclick = () => openBook(last, true);
  } else c.hidden = true;
}
function delLocal(b) {
  if (!confirm(`删除本地导入的《${b.title}》？`)) return;
  LS.set('td.local', LS.get('td.local', []).filter(x => x.id !== b.id)); loadBooks();
}

/* ---------------- 打开书 ---------------- */
async function openBook(meta, resume) {
  let book;
  try {
    if (meta.local) book = LS.get('td.local', []).find(x => x.id === meta.id);
    else { const r = await fetch(joinUrl(meta.base, meta.id + '/book.json')); if (!r.ok) throw 0; book = await r.json(); }
  } catch { return toast('打开失败：书库不可达'); }
  S.book = book; S.bookMeta = meta;
  const p = progOf(meta.key);
  $('#shelf').hidden = true; $('#reader').hidden = false;
  $('#rBook').textContent = book.title;
  history.pushState({ r: 1 }, '');
  loadChapter(p ? p.ch : 0, p ? p.si : 0, false);
}
function closeBook() {
  pause(); saveProg(); S.book = null; S.bookMeta = null;
  $('#reader').hidden = true; $('#shelf').hidden = false; renderShelf();
}

/* ---------------- 章节渲染 ---------------- */
function loadChapter(ci, si = 0, autoplay = false) {
  const book = S.book; if (!book) return;
  ci = Math.max(0, Math.min(book.chapters.length - 1, ci));
  pause(true);
  S.ch = ci; S.si = si;
  const ch = book.chapters[ci];
  $('#rChap').textContent = ch.title || `第 ${ci + 1} 章`;
  const box = $('#text'); box.innerHTML = '';
  const h = document.createElement('h2'); h.textContent = ch.title || `第 ${ci + 1} 章`; box.appendChild(h);
  S.flat = []; let idx = 0;
  ch.paras.forEach(pa => {
    const p = document.createElement('p');
    pa.forEach(t => {
      const sp = document.createElement('span'); sp.className = 's'; sp.textContent = t; const i = idx++;
      sp.onclick = () => { seekSentence(i); play(); };
      p.appendChild(sp); S.flat.push({ el: sp, text: t });
    });
    box.appendChild(p);
  });
  box.scrollTop = 0;
  S.times = ch.audio && ch.times ? ch.times : null;
  S.mode = S.times ? 'audio' : 'tts';
  if (S.mode === 'audio') {
    audio.src = joinUrl(S.bookMeta.base, S.book.id ? S.book.id + '/' + ch.audio : S.bookMeta.id + '/' + ch.audio);
    audio.playbackRate = S.speed; audio.preservesPitch = true;
    audio.load();
  } else { audio.removeAttribute('src'); audio.load(); }
  $('#modeTag').textContent = S.mode === 'audio' ? '🎧 高质量有声版' : '🔈 手机自带朗读（本书暂无预生成音频）';
  $('#seek').value = 0; $('#tCur').textContent = '0:00';
  $('#tTot').textContent = S.mode === 'audio' ? '--:--' : `${S.flat.length}句`;
  highlight(si, true);
  if (S.mode === 'audio' && si > 0) audio.addEventListener('loadedmetadata', function f() { audio.removeEventListener('loadedmetadata', f); audio.currentTime = S.times[si] / 1000; }, { once: true });
  renderChapNav(); setMedia(); saveProg();
  if (autoplay) play();
}
function renderChapNav() {
  const n = $('#chapNav'), last = S.ch >= S.book.chapters.length - 1;
  n.innerHTML = `${S.ch > 0 ? '<button id="cnPrev">上一章</button>' : ''}${!last ? '<button id="cnNext">下一章</button>' : ''}`;
  const a = $('#cnPrev'), b = $('#cnNext');
  if (a) a.onclick = () => loadChapter(S.ch - 1, 0, S.playing);
  if (b) b.onclick = () => loadChapter(S.ch + 1, 0, S.playing);
}
function highlight(i, noScroll) {
  i = Math.max(0, Math.min(S.flat.length - 1, i));
  if (S.flat[S.si]) S.flat[S.si].el.classList.remove('on');
  S.si = i;
  const cur = S.flat[i]; if (!cur) return;
  cur.el.classList.add('on');
  if (S.set.follow && !noScroll) {
    const box = $('#text'), r = cur.el.getBoundingClientRect(), b = box.getBoundingClientRect();
    if (r.top < b.top + 60 || r.bottom > b.bottom - 90) box.scrollTop += r.top - b.top - b.height * 0.33;
  } else if (noScroll && i > 0) {
    const box = $('#text'), r = cur.el.getBoundingClientRect(), b = box.getBoundingClientRect();
    box.style.scrollBehavior = 'auto'; box.scrollTop += r.top - b.top - b.height * 0.33; box.style.scrollBehavior = '';
  }
}

/* ---------------- 播放 ---------------- */
function sentenceAt(ms) {
  const t = S.times; let lo = 0, hi = t.length - 1;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (t[m] <= ms) lo = m; else hi = m - 1; }
  return lo;
}
function seekSentence(i) {
  i = Math.max(0, Math.min(S.flat.length - 1, i));
  if (S.mode === 'audio') { audio.currentTime = S.times[i] / 1000; highlight(i); }
  else { highlight(i); if (S.playing) speakFrom(i); }
}
function play() {
  if (!S.book) return;
  S.playing = true; $('#btnPlay').textContent = '⏸';
  if (S.mode === 'audio') {
    audio.playbackRate = S.speed;
    audio.play().catch(e => { S.playing = false; $('#btnPlay').textContent = '▶'; toast('无法播放：' + (e.message || e.name)); });
  } else speakFrom(S.si);
  if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';
}
function pause(silent) {
  S.playing = false; $('#btnPlay').textContent = '▶';
  if (!audio.paused) audio.pause();
  speechSynthesis.cancel(); S.ttsToken++;
  if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
  if (!silent) saveProg();
}
function toggle() { S.playing ? pause() : play(); }

audio.addEventListener('timeupdate', () => {
  if (S.mode !== 'audio' || !S.times) return;
  const ms = audio.currentTime * 1000, i = sentenceAt(ms);
  if (i !== S.si) { highlight(i); }
  const d = audio.duration || 0;
  $('#tCur').textContent = fmt(audio.currentTime); if (d) { $('#tTot').textContent = fmt(d); $('#seek').value = Math.round(audio.currentTime / d * 1000); }
  if (Math.floor(audio.currentTime) % 5 === 0) saveProg();
  checkSleep();
});
audio.addEventListener('loadedmetadata', () => { if (S.mode === 'audio') $('#tTot').textContent = fmt(audio.duration); });
audio.addEventListener('ended', () => { if (S.mode === 'audio') chapterEnded(); });
audio.addEventListener('error', () => { if (S.mode === 'audio' && S.book) { toast('音频加载失败，改用手机朗读'); S.mode = 'tts'; $('#modeTag').textContent = '🔈 手机自带朗读（音频不可用）'; if (S.playing) speakFrom(S.si); } });

function chapterEnded() {
  if (S.sleepEnd) { S.sleepEnd = false; setSleepLabel(); pause(); toast('已按定时在本章结束停止'); return; }
  if (S.ch < S.book.chapters.length - 1) loadChapter(S.ch + 1, 0, true);
  else { pause(); toast('全书读完啦'); }
}

/* 浏览器朗读 */
let voices = [];
function loadVoices() {
  voices = speechSynthesis.getVoices().filter(v => /^zh/i.test(v.lang));
  const sel = $('#voiceSel'); sel.innerHTML = '<option value="">自动（推荐）</option>' + voices.map(v => `<option value="${esc(v.name)}">${esc(v.name)}</option>`).join('');
  sel.value = S.set.voice || '';
}
if ('speechSynthesis' in window) { speechSynthesis.onvoiceschanged = loadVoices; loadVoices(); }
function pickVoice() {
  if (S.set.voice) { const v = voices.find(v => v.name === S.set.voice); if (v) return v; }
  return voices.find(v => /Tingting|Ting-Ting|Xiaoxiao|Xiaoyi|Huihui|Yunxi|Meijia|Google.*普通话|Chinese/i.test(v.name) && /CN|zh-CN|cmn/i.test(v.lang + v.name))
    || voices.find(v => /zh-CN|cmn/i.test(v.lang)) || voices[0];
}
function speakFrom(i) {
  speechSynthesis.cancel(); const tok = ++S.ttsToken;
  const one = (k) => {
    if (tok !== S.ttsToken || !S.playing) return;
    if (k >= S.flat.length) return chapterEnded();
    highlight(k);
    $('#seek').value = Math.round(k / S.flat.length * 1000); $('#tCur').textContent = `${k + 1}/${S.flat.length}`;
    const u = new SpeechSynthesisUtterance(S.flat[k].text);
    const v = pickVoice(); if (v) { u.voice = v; u.lang = v.lang; } else u.lang = 'zh-CN';
    u.rate = S.speed;
    u.onend = () => { if (tok === S.ttsToken) { saveProg(); checkSleep(); one(k + 1); } };
    u.onerror = e => { if (e.error !== 'canceled' && e.error !== 'interrupted' && tok === S.ttsToken) { pause(); toast('朗读出错：' + e.error); } };
    speechSynthesis.speak(u);
  };
  one(i);
}

/* 定时 / 倍速 / 控件 */
function checkSleep() {
  if (S.sleepAt && Date.now() >= S.sleepAt) { S.sleepAt = 0; setSleepLabel(); pause(); toast('定时已到，晚安 😴'); }
}
function setSleepLabel() {
  const b = $('#btnSleep');
  if (S.sleepEnd) b.textContent = '本章止'; else if (S.sleepAt) b.textContent = Math.ceil((S.sleepAt - Date.now()) / 60000) + '分'; else b.textContent = '定时';
  b.classList.toggle('active', !!(S.sleepAt || S.sleepEnd));
}
setInterval(() => { if (S.sleepAt) { checkSleep(); setSleepLabel(); } }, 15000);
function setSpeed(v) {
  S.speed = v; LS.set('td.speed', v); audio.playbackRate = v;
  const b = $('#btnSpeed'); b.textContent = v.toFixed(v % 1 ? 2 : 1).replace(/0$/, '') + 'x'; b.classList.toggle('active', v !== 1);
  if (S.mode === 'tts' && S.playing) speakFrom(S.si);
}
function skip(sec) {
  if (S.mode === 'audio') audio.currentTime = Math.max(0, Math.min(audio.duration || 1e9, audio.currentTime + sec));
  else seekSentence(S.si + (sec > 0 ? 3 : -3));
}

/* 锁屏控制 */
function setMedia() {
  if (!('mediaSession' in navigator) || !S.book) return;
  const ch = S.book.chapters[S.ch];
  navigator.mediaSession.metadata = new MediaMetadata({ title: ch.title || `第${S.ch + 1}章`, artist: S.book.author || '', album: S.book.title,
    artwork: [{ src: new URL('icon-512.png', location.href).href, sizes: '512x512', type: 'image/png' }] });
  const h = navigator.mediaSession.setActionHandler.bind(navigator.mediaSession);
  const safe = (a, f) => { try { h(a, f); } catch {} };
  safe('play', play); safe('pause', () => pause());
  safe('previoustrack', () => loadChapter(S.ch - 1, 0, true)); safe('nexttrack', () => loadChapter(S.ch + 1, 0, true));
  safe('seekbackward', () => skip(-15)); safe('seekforward', () => skip(15));
}

/* ---------------- 抽屉 ---------------- */
function openSheet(id) { $('#sheetMask').hidden = false; $(id).hidden = false; }
function closeSheets() { $('#sheetMask').hidden = true; $$('.sheet').forEach(s => (s.hidden = true)); }
function openToc() {
  const ol = $('#tocList'); ol.innerHTML = '';
  S.book.chapters.forEach((c, i) => {
    const li = document.createElement('li'); if (i === S.ch) li.className = 'cur';
    const n = c.paras.reduce((a, p) => a + p.join('').length, 0);
    li.innerHTML = `<span>${esc(c.title || '第' + (i + 1) + '章')}</span><small>${c.audio ? '🎧 ' : ''}${n > 9999 ? (n / 10000).toFixed(1) + '万字' : n + '字'}</small>`;
    li.onclick = () => { closeSheets(); loadChapter(i, 0, S.playing); };
    ol.appendChild(li);
  });
  openSheet('#sheetToc');
  const cur = $('#tocList .cur'); if (cur) cur.scrollIntoView({ block: 'center' });
}
function applySet() {
  document.body.dataset.theme = S.set.theme;
  document.documentElement.style.setProperty('--fs', S.set.fs + 'px');
  document.documentElement.style.setProperty('--lh', S.set.lh);
  $('#fontVal').textContent = S.set.fs;
  $$('#segTheme button').forEach(b => b.classList.toggle('on', b.dataset.v === S.set.theme));
  $$('#segLH button').forEach(b => b.classList.toggle('on', +b.dataset.v === +S.set.lh));
  $$('#segFollow button').forEach(b => b.classList.toggle('on', +b.dataset.v === +S.set.follow));
  const meta = document.querySelector('meta[name=theme-color]'); meta.content = { paper: '#f6f1e7', green: '#dfeadb', night: '#16181c' }[S.set.theme];
  LS.set('td.set', S.set);
}

/* ---------------- TXT 导入 ---------------- */
function splitSentences(text) {
  const out = []; let buf = '';
  for (const ch of text) {
    buf += ch;
    if (/[。！？!?；…]/.test(ch) || (ch === '.' && false)) { out.push(buf); buf = ''; }
  }
  if (buf.trim()) out.push(buf);
  const merged = [];
  for (const s of out) { if (merged.length && (merged[merged.length - 1].length < 14 || /^[”’」』）)]+$/.test(s.trim()))) merged[merged.length - 1] += s; else merged.push(s); }
  return merged.map(s => s.trim()).filter(Boolean);
}
function parseTxt(name, text) {
  text = text.replace(/\r/g, '').replace(/\u3000/g, ' ');
  const lines = text.split('\n');
  const headRe = /^\s*(第[零一二三四五六七八九十百千两\d]+[章节回篇卷部]|Chapter\s+\d+|序章|序言|前言|后记|尾声|楔子)/i;
  const chapters = []; let cur = { title: '开篇', lines: [] };
  for (const ln of lines) {
    if (headRe.test(ln) && ln.trim().length < 40) { if (cur.lines.join('').trim()) chapters.push(cur); cur = { title: ln.trim(), lines: [] }; }
    else cur.lines.push(ln);
  }
  if (cur.lines.join('').trim()) chapters.push(cur);
  let chs = chapters;
  if (chs.length <= 1) { // 无章节标记：按约 3000 字切段
    const paras = lines.map(l => l.trim()).filter(Boolean); chs = []; let acc = [], n = 0;
    for (const p of paras) { acc.push(p); n += p.length; if (n > 3000) { chs.push({ title: `第 ${chs.length + 1} 部分`, lines: acc }); acc = []; n = 0; } }
    if (acc.length) chs.push({ title: `第 ${chs.length + 1} 部分`, lines: acc });
  }
  return { id: 'local-' + Date.now().toString(36), title: name.replace(/\.[^.]+$/, ''), author: '本地导入',
    chapters: chs.map(c => ({ title: c.title, paras: c.lines.map(l => l.trim()).filter(Boolean).map(splitSentences).filter(p => p.length) })) };
}
async function importTxt(file) {
  const buf = await file.arrayBuffer(); let text;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(buf); } catch { text = new TextDecoder('gb18030').decode(buf); }
  const b = parseTxt(file.name, text);
  if (!b.chapters.length) return toast('没有读到文字');
  const l = LS.get('td.local', []); l.push(b); LS.set('td.local', l);
  toast(`已导入《${b.title}》${b.chapters.length}章`); loadBooks();
}

/* ---------------- 事件 ---------------- */
function bind() {
  $('#btnPlay').onclick = toggle;
  $('#btnPrev').onclick = () => loadChapter(S.ch - 1, 0, S.playing);
  $('#btnNext').onclick = () => loadChapter(S.ch + 1, 0, S.playing);
  $('#btnBack15').onclick = () => skip(-15); $('#btnFwd15').onclick = () => skip(15);
  $('#btnBack').onclick = () => history.back();
  window.addEventListener('popstate', () => { if (S.book) closeBook(); closeSheets(); });
  $('#btnToc').onclick = openToc; $('#btnSet').onclick = () => openSheet('#sheetSet');
  $('#sheetMask').onclick = closeSheets; $$('[data-close]').forEach(b => (b.onclick = closeSheets));
  const seek = $('#seek');
  seek.oninput = () => {
    if (S.mode === 'audio' && audio.duration) { audio.currentTime = seek.value / 1000 * audio.duration; $('#tCur').textContent = fmt(audio.currentTime); }
    else if (S.mode === 'tts') seekSentence(Math.floor(seek.value / 1000 * (S.flat.length - 1)));
  };
  $('#btnSpeed').onclick = () => { const g = $('#speedList'); g.innerHTML = ''; SPEEDS.forEach(v => { const b = document.createElement('button'); b.textContent = v + 'x'; if (v === S.speed) b.className = 'on'; b.onclick = () => { setSpeed(v); closeSheets(); }; g.appendChild(b); }); openSheet('#sheetSpeed'); };
  $('#btnSleep').onclick = () => { const g = $('#sleepList'); g.innerHTML = ''; SLEEPS.forEach(([n, m]) => { const b = document.createElement('button'); b.textContent = n; b.onclick = () => {
    S.sleepAt = 0; S.sleepEnd = false; if (m > 0) S.sleepAt = Date.now() + m * 60000; if (m < 0) S.sleepEnd = true; setSleepLabel(); closeSheets(); if (m) toast(m > 0 ? `${m} 分钟后停止播放` : '本章结束后停止'); }; g.appendChild(b); }); openSheet('#sheetSleep'); };
  $$('#segTheme button').forEach(b => (b.onclick = () => { S.set.theme = b.dataset.v; applySet(); }));
  $$('#segLH button').forEach(b => (b.onclick = () => { S.set.lh = +b.dataset.v; applySet(); }));
  $$('#segFollow button').forEach(b => (b.onclick = () => { S.set.follow = +b.dataset.v; applySet(); }));
  $$('#segFont button').forEach(b => (b.onclick = () => { S.set.fs = Math.max(14, Math.min(30, S.set.fs + +b.dataset.v)); applySet(); }));
  $('#voiceSel').onchange = e => { S.set.voice = e.target.value; applySet(); if (S.mode === 'tts' && S.playing) speakFrom(S.si); };
  $('#btnImport').onclick = () => $('#fileInput').click();
  $('#fileInput').onchange = e => { const f = e.target.files[0]; if (f) importTxt(f); e.target.value = ''; };
  $('#linkLib').onclick = e => { e.preventDefault(); const u = prompt('粘贴私人书库地址（以 / 结尾，里面有 index.json）：'); if (u) { const l = LS.get('td.libs', []); if (!l.includes(u)) l.push(u); LS.set('td.libs', l); S.libs = ['./library/', ...l]; loadBooks(); toast('已添加书库'); } };
  document.addEventListener('keydown', e => {
    if (!S.book || /INPUT|SELECT/.test(e.target.tagName)) return;
    if (e.code === 'Space') { e.preventDefault(); toggle(); } else if (e.code === 'ArrowRight') skip(15); else if (e.code === 'ArrowLeft') skip(-15);
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) saveProg(); });
}

/* ---------------- 启动 ---------------- */
initLibs(); applySet(); bind(); setSpeed(S.speed); loadBooks();
if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('sw.js').catch(() => {});
window.__td = S; // 便于调试
})();
