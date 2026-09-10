from __future__ import annotations
import base64, errno, hashlib, json, mimetypes, os, struct, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .models import normalize, verify_read_only
from .storage import Store

STATIC=Path(__file__).resolve().parent/'static'
class MissionControl:
    def __init__(self,source,db_path:str,interval:float=2.0):
        self.source=source; self.store=Store(db_path); self.interval=interval; self.lock=threading.RLock(); self.latest={}; self.error=None; self.stop_event=threading.Event()
    def poll_once(self):
        raw=self.source.read(); snap=normalize(raw); snap['sample_utc']=time.time(); snap['errors']=verify_read_only(snap)
        with self.lock: self.latest=snap; self.error=None
        self.store.persist(snap); return snap
    def loop(self):
        while not self.stop_event.is_set():
            try: self.poll_once()
            except Exception as exc:
                with self.lock: self.error=str(exc)[:1000]
            self.stop_event.wait(self.interval)
    def state(self):
        with self.lock: return {'ok':self.error is None,'error':self.error,'state':dict(self.latest)}

def _frame(payload:bytes)->bytes:
    n=len(payload)
    if n<126: return bytes([0x81,n])+payload
    if n<65536: return bytes([0x81,126])+struct.pack('!H',n)+payload
    return bytes([0x81,127])+struct.pack('!Q',n)+payload

def make_handler(mc:MissionControl):
    class H(BaseHTTPRequestHandler):
        server_version='LION-Mission-Control/1.0'
        def log_message(self,*a): pass
        def send_json(self,obj,code=200):
            b=json.dumps(obj,sort_keys=True,separators=(',',':')).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            path=self.path.split('?',1)[0]
            if path=='/api/state': return self.send_json(mc.state())
            if path=='/api/export': return self.send_json(mc.store.export())
            if path=='/health': return self.send_json({'ok':mc.error is None,'error':mc.error})
            if path=='/ws' and self.headers.get('Upgrade','').lower()=='websocket':
                key=self.headers.get('Sec-WebSocket-Key',''); accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode(),usedforsecurity=False).digest()).decode(); self.send_response(101); self.send_header('Upgrade','websocket'); self.send_header('Connection','Upgrade'); self.send_header('Sec-WebSocket-Accept',accept); self.end_headers()
                try:
                    while not mc.stop_event.is_set(): self.wfile.write(_frame(json.dumps(mc.state(),sort_keys=True,separators=(',',':')).encode())); self.wfile.flush(); time.sleep(1)
                except Exception: pass
                return
            rel='index.html' if path=='/' else path.lstrip('/')
            target=(STATIC/rel).resolve()
            if STATIC.resolve() not in target.parents and target!=STATIC.resolve(): self.send_error(403); return
            if not target.is_file(): self.send_error(404); return
            b=target.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(str(target))[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
    return H

def serve(mc:MissionControl,host='127.0.0.1',port=8765,fallback_ports=(),listen_state=None):
    candidates=[]
    for candidate in (port,*fallback_ports):
        candidate=int(candidate)
        if candidate not in candidates: candidates.append(candidate)
    httpd=None; selected=None
    for candidate in candidates:
        try:
            httpd=ThreadingHTTPServer((host,candidate),make_handler(mc)); selected=candidate; break
        except OSError as exc:
            if exc.errno!=errno.EADDRINUSE: raise
    if httpd is None or selected is None:
        raise OSError(errno.EADDRINUSE,'no Mission Control port available in bounded candidate set')
    state_path=Path(listen_state) if listen_state else None
    if state_path is not None:
        state_path.parent.mkdir(parents=True,exist_ok=True)
        tmp=state_path.with_suffix(state_path.suffix+'.tmp')
        tmp.write_text(json.dumps({'host':host,'port':selected,'pid':os.getpid(),'status':'LISTENING'},sort_keys=True)+'\n')
        os.replace(tmp,state_path)
        os.chmod(state_path,0o644)
    t=threading.Thread(target=mc.loop,daemon=True); t.start()
    try: httpd.serve_forever()
    finally:
        mc.stop_event.set(); httpd.server_close()
        if state_path is not None:
            try: state_path.unlink()
            except FileNotFoundError: pass