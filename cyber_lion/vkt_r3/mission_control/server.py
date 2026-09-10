from __future__ import annotations
import base64, errno, hashlib, json, mimetypes, os, struct, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .models import normalize
STATIC=Path(__file__).resolve().parent/'static'
class MissionControl:
    def __init__(self,source,store,interval=2.0): self.source=source; self.store=store; self.interval=interval; self.stop=threading.Event(); self.error=None
    def poll_once(self):
        raw=self.source(); state=normalize(raw); self.store.record(state,raw); return state
    def loop(self):
        while not self.stop.is_set():
            try: self.poll_once(); self.error=None
            except Exception as e: self.error=str(e)[:1000]
            self.stop.wait(self.interval)
    def health(self):
        return {'ok':self.error is None,'error':self.error,'latest':self.store.latest(),'samples':len(self.store.samples()),'evidence_events':self.store.event_count()}
def _frame(b):
    n=len(b)
    if n<126:return bytes([0x81,n])+b
    if n<65536:return bytes([0x81,126])+struct.pack('!H',n)+b
    return bytes([0x81,127])+struct.pack('!Q',n)+b
def make_handler(mc):
    class H(BaseHTTPRequestHandler):
        server_version='LION-VKT-Mission-Control/1.0'
        def log_message(self,*a): pass
        def json_response(self,obj,code=200):
            b=json.dumps(obj,sort_keys=True,separators=(',',':')).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/health': return self.json_response(mc.health())
            if path=='/api/current': return self.json_response(mc.store.latest() or {})
            if path=='/api/samples': return self.json_response({'samples':mc.store.samples()})
            if path=='/api/events': return self.json_response({'events':mc.store.recent_events()})
            if path=='/api/export': return self.json_response(mc.store.export())
            if path=='/ws' and self.headers.get('Upgrade','').lower()=='websocket':
                key=self.headers.get('Sec-WebSocket-Key',''); accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode(),usedforsecurity=False).digest()).decode(); self.send_response(101); self.send_header('Upgrade','websocket'); self.send_header('Connection','Upgrade'); self.send_header('Sec-WebSocket-Accept',accept); self.end_headers()
                try:
                    while not mc.stop.is_set(): self.wfile.write(_frame(json.dumps({'state':mc.store.latest(),'error':mc.error}).encode())); self.wfile.flush(); time.sleep(1)
                except Exception: pass
                return
            rel='index.html' if path=='/' else path.lstrip('/'); target=(STATIC/rel).resolve()
            if STATIC.resolve() not in target.parents and target!=STATIC.resolve(): return self.send_error(403)
            if not target.is_file(): return self.send_error(404)
            b=target.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(str(target))[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
        def _deny(self): self.json_response({'ok':False,'error':'read-only observer'},405)
        do_POST=do_PUT=do_PATCH=do_DELETE=lambda self:self._deny()
    return H
def serve(mc,host='127.0.0.1',port=8765,fallback_ports=(),listen_state=None):
    ports=[]
    for item in (port,*fallback_ports):
        value=int(item)
        if value not in ports: ports.append(value)
    httpd=None; selected=None
    for value in ports:
        try: httpd=ThreadingHTTPServer((host,value),make_handler(mc)); selected=value; break
        except OSError as exc:
            if exc.errno!=errno.EADDRINUSE: raise
    if httpd is None: raise OSError(errno.EADDRINUSE,'no configured mission-control port available')
    if listen_state:
        path=Path(listen_state); path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+'.tmp'); temp.write_text(json.dumps({'host':host,'port':selected,'pid':os.getpid(),'status':'LISTENING'},sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8'); os.replace(temp,path); os.chmod(path,0o644)
    thread=threading.Thread(target=mc.loop,daemon=True); thread.start()
    try: httpd.serve_forever()
    finally: mc.stop.set(); httpd.shutdown(); httpd.server_close(); thread.join(timeout=5)
