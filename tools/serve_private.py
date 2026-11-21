#!/usr/bin/env python3
"""私人书库静态服务：支持 Range（音频拖动必需）+ CORS，URL 带一段随机令牌当门禁。
用法: python3 tools/serve_private.py <目录> [端口]   令牌读自 <目录>/.token（没有就生成）。
"""
import http.server, os, re, secrets, sys, socketserver
from pathlib import Path

root = Path(sys.argv[1]).resolve(); port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
tf = root / '.token'
if not tf.exists(): tf.write_text(secrets.token_urlsafe(12))
TOKEN = tf.read_text().strip()

class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split('?', 1)[0]
        pre = f'/{TOKEN}/'
        if not path.startswith(pre): return str(root / '.forbidden')
        return str(root / path[len(pre):].lstrip('/'))
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-cache'); super().end_headers()
    def do_OPTIONS(self):
        self.send_response(204); self.send_header('Access-Control-Allow-Headers', 'Range'); self.end_headers()
    def send_head(self):
        p = Path(self.translate_path(self.path))
        rng = self.headers.get('Range')
        if not rng or not p.is_file(): return super().send_head()
        m = re.match(r'bytes=(\d*)-(\d*)', rng)
        size = p.stat().st_size
        a = int(m.group(1)) if m.group(1) else 0
        b = int(m.group(2)) if m.group(2) else size - 1
        b = min(b, size - 1)
        if a > b: self.send_error(416); return None
        f = open(p, 'rb'); f.seek(a)
        self.send_response(206); self.send_header('Content-Type', self.guess_type(str(p)))
        self.send_header('Content-Range', f'bytes {a}-{b}/{size}'); self.send_header('Content-Length', str(b - a + 1)); self.end_headers()
        self._range_left = b - a + 1
        return f
    def copyfile(self, src, dst):
        left = getattr(self, '_range_left', None)
        if left is None: return super().copyfile(src, dst)
        while left > 0:
            buf = src.read(min(65536, left))
            if not buf: break
            try: dst.write(buf)
            except (BrokenPipeError, ConnectionResetError): break
            left -= len(buf)
        self._range_left = None
    def log_message(self, *a): pass

class T(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True; allow_reuse_address = True
print(f'serving {root} on :{port}  token path /{TOKEN}/', flush=True)
T(('127.0.0.1', port), H).serve_forever()
