import http.client
import json
import re
import threading
import unittest
from http.server import ThreadingHTTPServer

from cyber_lion.app_coordination.local_intelligence_gateway import make_handler


class FakeGateway:
    thread_provider=None;control_provider=None
    def __init__(self):self.commands=[]
    def state(self):return {'status':'ok','authority_effect':'NONE'}
    def operator_provider(self,op,args):
        if op=='pair':return {'paired':True,'principal_id':'OPERATOR_PRIMARY','session_token':'gateway-session','expires_at_epoch':99999999999}
        if op=='session':return {'paired':args.get('session_token')=='gateway-session','principal_id':'OPERATOR_PRIMARY' if args.get('session_token')=='gateway-session' else 'OPERATOR_PANEL_PROXY'}
        if op=='participants':return {'participant':{'principal_id':'OPERATOR_PRIMARY'}}
        if op=='state':return {'control':{'control_owner':'AUTONOMOUS','control_epoch':1,'pause_latch':0,'stop_latch':0,'context_revision':0,'plan_revision':0},'messages':[]}
        if op=='events':return {'events':[],'next_cursor':int(args.get('after',0))}
        if op=='command':
            if args.pop('__session_token',None)!='gateway-session':raise ValueError('gateway session missing')
            self.commands.append(args);return {'command_id':args['command_id'],'admission_state':'ACCEPTED','execution_state':'APPLIED','observation_state':'PERSISTED'}
        if op=='command_status':return {'command_id':args['command_id']}
        if op=='ack':return args
        raise AssertionError(op)


class OperatorPanelSecurityTests(unittest.TestCase):
    def setUp(self):
        self.g=FakeGateway();self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.g));self.port=self.server.server_address[1]
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def raw(self,method,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3);h=dict(headers or {})
        data=None
        if body is not None:data=json.dumps(body).encode();h['Content-Type']='application/json'
        c.request(method,path,body=data,headers=h);r=c.getresponse();raw=r.read();heads=dict(r.getheaders());c.close();return r.status,heads,raw
    def bootstrap(self):
        status,headers,body=self.raw('GET','/');self.assertEqual(status,200)
        cookie=headers.get('Set-Cookie');self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
        session=cookie.split(';',1)[0]
        html=body.decode();csrf=re.search(r"const OPERATOR_CSRF='([^']+)'",html).group(1)
        self.assertNotIn('X-LION-Operator-Key',html)
        return session,csrf
    def test_operator_api_requires_browser_session(self):
        status,_,_=self.raw('GET','/api/operator/state?mission_id=M1');self.assertEqual(status,403)
        session,csrf=self.bootstrap();status,_,_=self.raw('GET','/api/operator/state?mission_id=M1',headers={'Cookie':session});self.assertEqual(status,403)
        status,_,_=self.raw('POST','/api/operator/pair',{'pairing_code':'local-human-code'},{'Cookie':session,'X-LION-CSRF':csrf,'Origin':f'http://127.0.0.1:{self.port}'});self.assertEqual(status,201)
        status,_,body=self.raw('GET','/api/operator/state?mission_id=M1',headers={'Cookie':session});self.assertEqual(status,200);self.assertEqual(json.loads(body)['control']['control_epoch'],1)
    def test_mutation_requires_csrf_and_local_origin(self):
        session,csrf=self.bootstrap();body={'command_id':'c1','mission_id':'M1','action':'TAKE_CONTROL','target':'mission:M1','payload':{}}
        status,_,_=self.raw('POST','/api/operator/commands',body,{'Cookie':session});self.assertEqual(status,403)
        status,_,_=self.raw('POST','/api/operator/commands',body,{'Cookie':session,'X-LION-CSRF':csrf,'Origin':'https://evil.example'});self.assertEqual(status,403)
        # Valid browser session and CSRF still do not confer OPERATOR_PRIMARY before explicit pairing.
        status,_,_=self.raw('POST','/api/operator/commands',body,{'Cookie':session,'X-LION-CSRF':csrf,'Origin':f'http://127.0.0.1:{self.port}'});self.assertEqual(status,403)
        status,_,paired=self.raw('POST','/api/operator/pair',{'pairing_code':'local-human-code'},{'Cookie':session,'X-LION-CSRF':csrf,'Origin':f'http://127.0.0.1:{self.port}'});self.assertEqual(status,201);self.assertTrue(json.loads(paired)['paired']);self.assertNotIn(b'gateway-session',paired)
        status,_,raw=self.raw('POST','/api/operator/commands',body,{'Cookie':session,'X-LION-CSRF':csrf,'Origin':f'http://127.0.0.1:{self.port}'});self.assertEqual(status,201);self.assertEqual(json.loads(raw)['command_id'],'c1');self.assertEqual(len(self.g.commands),1)


if __name__=='__main__':unittest.main()
