from __future__ import annotations

import importlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest


ROOT=Path(__file__).resolve().parents[2]
TRANSPORT_DIR=ROOT/"LION/runtime_compat/r24/docker-autonomy"
if str(TRANSPORT_DIR) not in sys.path:
    sys.path.insert(0,str(TRANSPORT_DIR))

from transport import PersistentJsonTransport


class CountingHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=32

    def __init__(self,*args,**kwargs):
        self.accept_count=0
        super().__init__(*args,**kwargs)

    def get_request(self):
        sock,addr=super().get_request()
        self.accept_count+=1
        return sock,addr


class KeepAliveHandler(BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"

    def log_message(self,*args):
        return

    def do_GET(self):
        body=json.dumps({"ok":True,"path":self.path},sort_keys=True).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CloseHandler(KeepAliveHandler):
    def do_GET(self):
        body=b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Connection","close")
        self.end_headers()
        self.wfile.write(body)


class R24PersistentWorkerTransportTests(unittest.TestCase):
    def run_server(self,handler):
        srv=CountingHTTPServer(("127.0.0.1",0),handler)
        th=threading.Thread(target=srv.serve_forever,daemon=True)
        th.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv

    def test_three_json_requests_reuse_one_tcp_connection(self):
        srv=self.run_server(KeepAliveHandler)
        transport=PersistentJsonTransport(user_agent="test",resolver=lambda host:"127.0.0.1")
        self.addCleanup(transport.close)
        url=f"http://example.invalid:{srv.server_port}/probe"
        for i in range(3):
            out=transport.request_json(url+"?i="+str(i),timeout=2)
            self.assertTrue(out["ok"])
        self.assertEqual(srv.accept_count,1)
        self.assertEqual(transport.connection_creations,1)
        self.assertEqual(transport.open_connections,1)

    def test_server_close_is_observed_and_next_request_reconnects(self):
        srv=self.run_server(CloseHandler)
        transport=PersistentJsonTransport(user_agent="test",resolver=lambda host:"127.0.0.1")
        self.addCleanup(transport.close)
        url=f"http://example.invalid:{srv.server_port}/probe"
        self.assertTrue(transport.request_json(url,timeout=2)["ok"])
        self.assertEqual(transport.open_connections,0)
        self.assertTrue(transport.request_json(url,timeout=2)["ok"])
        self.assertEqual(srv.accept_count,2)
        self.assertEqual(transport.connection_creations,2)

    def test_mission_control_http_server_is_keepalive_ready(self):
        tools=ROOT/"tools"
        if str(tools) not in sys.path:
            sys.path.insert(0,str(tools))
        compat=importlib.import_module("lion_mission_control_compat")
        sys.modules["mission_control_compat"]=compat
        mc=importlib.import_module("lion_mission_control_v3")
        self.assertEqual(mc.H.protocol_version,"HTTP/1.1")
        self.assertGreaterEqual(mc.FleetThreadingHTTPServer.request_queue_size,128)
        self.assertTrue(mc.FleetThreadingHTTPServer.daemon_threads)


if __name__=="__main__":
    unittest.main()
