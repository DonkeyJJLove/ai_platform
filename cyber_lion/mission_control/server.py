from __future__ import annotations
import base64,errno,hashlib,json,mimetypes,os,struct,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .models import clean_run
STATIC=Path(__file__).resolve().parent/'static'
STATIC_FILES={'/':STATIC/'index.html','/index.html':STATIC/'index.html','/app.js':STATIC/'app.js','/app.css':STATIC/'app.css'}
class MissionControl:
 def __init__(self,registry,store,interval=2.0):self.registry=registry;self.store=store;self.interval=interval;self.stop=threading.Event();self.error=None
 def poll_once(self):
  for r in self.registry.discover():self.store.index_run(clean_run(r))
  return self.store.runs()
 def loop(self):
  while not self.stop.is_set():
   try:self.poll_once();self.error=None
   except Exception as e:self.error=str(e)[:1000]
   self.stop.wait(self.interval)
 def summary(self):
  rs=self.store.runs();return {'active_runs':sum(r['status'] in {'STARTING','RUNNING','CLEANING'} for r in rs),'completed_runs':sum(r['status'] in {'PASS','CLEANED'} for r in rs),'failed_runs':sum(r['status']=='FAIL' for r in rs),'deferred_runs':sum(r['status']=='DEFER' for r in rs),'hosts':len({r.get('host') for r in rs if r.get('host')}),'workloads':len(rs),'events':sum(len(self.store.events(r['run_id'])) for r in rs),'artifacts':sum(r.get('artifact_count',0) for r in rs)}
def _frame(b):
 n=len(b);return bytes([0x81,n])+b if n<126 else bytes([0x81,126])+struct.pack('!H',n)+b if n<65536 else bytes([0x81,127])+struct.pack('!Q',n)+b
def make_handler(mc):
 class H(BaseHTTPRequestHandler):
  server_version='LION-Mission-Control/2.0'
  def log_message(self,*a):pass
  def js(self,o,c=200):
   b=json.dumps(o,sort_keys=True,separators=(',',':')).encode();self.send_response(c);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
  def deny(self):self.js({'ok':False,'error':'read-only'},405)
  do_POST=do_PUT=do_PATCH=do_DELETE=lambda self:self.deny()
  def do_GET(self):
   p=self.path.split('?',1)[0]
   if p=='/health':return self.js({'ok':mc.error is None,'error':mc.error,'product':'LION Mission Control'})
   if p=='/api/summary':return self.js(mc.summary())
   if p=='/api/adapters':return self.js({'adapters':mc.registry.ids()})
   if p=='/api/runs':return self.js({'runs':mc.store.runs()})
   if p=='/api/export':return self.js({'runs':mc.store.runs()})
   if p.startswith('/api/export/'):
    rid=p[len('/api/export/'):];x=mc.store.export_run(rid);return self.js(x if x else {'error':'not found'},200 if x else 404)
   if p.startswith('/api/runs/'):
    q=p[len('/api/runs/'):].split('/');rid=q[0];r=mc.store.run(rid)
    if not r:return self.js({'error':'not found'},404)
    if len(q)==1:return self.js(r)
    kind=q[1]
    if kind=='events':return self.js({'events':mc.store.events(rid)})
    if kind=='metrics':return self.js({'metrics':mc.store.metrics(rid)})
    if kind=='participants':return self.js({'participants':mc.store.participants(rid)})
    if kind=='artifacts':return self.js({'artifacts':mc.store.artifacts(rid)})
    if kind=='receipts':return self.js({'receipts':mc.store.receipts(rid)})
   if p=='/ws' and self.headers.get('Upgrade','').lower()=='websocket':
    key=self.headers.get('Sec-WebSocket-Key','');acc=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode(),usedforsecurity=False).digest()).decode();self.send_response(101);self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.send_header('Sec-WebSocket-Accept',acc);self.end_headers()
    try:
     while not mc.stop.is_set():self.wfile.write(_frame(json.dumps({'summary':mc.summary()}).encode()));self.wfile.flush();time.sleep(1)
    except Exception:pass
    return
   f=STATIC_FILES.get(p)
   if not f or not f.is_file():return self.send_error(404)
   b=f.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(f))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 return H
def serve(mc,host='127.0.0.1',ports=range(8765,8776),listen_state='/run/lion-mission-control/listen.json'):
 httpd=None;selected=None
 for p in ports:
  try:httpd=ThreadingHTTPServer((host,int(p)),make_handler(mc));selected=int(p);break
  except OSError as e:
   if e.errno!=errno.EADDRINUSE:raise
 if httpd is None:raise OSError(errno.EADDRINUSE,'no bounded port')
 path=Path(listen_state);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps({'host':host,'port':selected,'pid':os.getpid(),'status':'LISTENING'})+'\n');os.replace(tmp,path);os.chmod(path,0o644);threading.Thread(target=mc.loop,daemon=True).start()
 try:httpd.serve_forever()
 finally:mc.stop.set();httpd.server_close()
