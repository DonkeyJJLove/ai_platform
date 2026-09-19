import json,subprocess,sys,tempfile,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

class H(BaseHTTPRequestHandler):
    seen=[]
    def log_message(self,*a):pass
    def do_GET(self):self.respond()
    def do_POST(self):
        n=int(self.headers.get('Content-Length','0'));body=json.loads(self.rfile.read(n) or b'{}');self.seen.append((self.headers.get('X-LION-Operator-Proxy-Key'),self.headers.get('X-LION-Operator-Key'),body));self.respond()
    def respond(self):
        if self.headers.get('X-LION-Operator-Proxy-Key')!='p'*64:self.send_response(403);raw=b'{"error":"proxy required"}'
        else:self.send_response(200);raw=b'{"ok":true}'
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

class OperatorClientTests(unittest.TestCase):
    def test_client_uses_proxy_identity_and_bounded_action_vocabulary(self):
        with tempfile.TemporaryDirectory() as td:
            key=Path(td)/'key';key.write_text('p'*64);srv=ThreadingHTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
            try:
                cmd=[sys.executable,'tools/lion_operator_client.py','--base',f'http://127.0.0.1:{srv.server_address[1]}','--key-file',str(key),'intervene','M','STOP_SCOPE','--command-id','c']
                run=subprocess.run(cmd,cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=10);self.assertEqual(run.returncode,0,run.stderr)
                proxy,primary,body=H.seen[-1];self.assertEqual(proxy,'p'*64);self.assertIsNone(primary);self.assertEqual(body['action'],'STOP_SCOPE')
                bad=subprocess.run(cmd[:-3]+['RESUME_SCOPE','--command-id','x'],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=10);self.assertNotEqual(bad.returncode,0)
            finally:srv.shutdown();srv.server_close();t.join(timeout=2)
if __name__=='__main__':unittest.main()
