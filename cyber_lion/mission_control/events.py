from __future__ import annotations
import json,os,socket,struct,threading
from .schema import validate_event
class EventSocket:
 def __init__(self,path,store,max_message=65536):self.path=path;self.store=store;self.max_message=max_message;self.stop=threading.Event();self.sock=None
 def start(self):
  os.makedirs(os.path.dirname(self.path),exist_ok=True)
  try:os.unlink(self.path)
  except FileNotFoundError:pass
  s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.bind(self.path);os.chmod(self.path,0o660)  # nosec B103 - LPCL requires group-writable local observation socket; SO_PEERCRED enforces uid
  s.listen(8);self.sock=s;threading.Thread(target=self._loop,daemon=True).start()
 def _loop(self):
  while not self.stop.is_set():
   try:c,_=self.sock.accept()
   except OSError:return
   with c:
    if hasattr(socket,'SO_PEERCRED'):
     _,uid,_=struct.unpack('3i',c.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
     if uid not in (0,os.getuid()):continue
    data=c.recv(self.max_message+1)
    if len(data)>self.max_message:continue
    try:self.store.add_event(validate_event(json.loads(data.decode())))
    except Exception:continue
 def close(self):
  self.stop.set()
  if self.sock:self.sock.close()
