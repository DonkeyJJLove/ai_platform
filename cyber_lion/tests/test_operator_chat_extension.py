from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path

from cyber_lion.app_coordination import operator_chat_extension as ext
from cyber_lion.app_coordination import operator_chat_store as store


class ThreadProvider:
    def __init__(self,path):
        self.path=Path(path)
        c=sqlite3.connect(self.path)
        c.executescript('''
        CREATE TABLE threads(thread_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
        CREATE TABLE messages(message_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,seq INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,meta_json TEXT NOT NULL,UNIQUE(thread_id,seq));
        ''')
        c.execute('INSERT INTO threads VALUES(?,?,?,?)',('a'*32,'Nowa rozmowa',1.0,1.0));c.commit();c.close()
    def __call__(self,op,args):
        if op!='append_assistant_once':raise AssertionError(op)
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row
        try:
            tid=args['thread_id'];key=args['dedupe_key']
            for r in c.execute("SELECT message_id,meta_json FROM messages WHERE thread_id=? AND role='assistant'",(tid,)):
                if json.loads(r['meta_json']).get('external_receipt_key')==key:return {'inserted':False,'message_id':r['message_id']}
            seq=c.execute('SELECT COALESCE(MAX(seq),0) FROM messages WHERE thread_id=?',(tid,)).fetchone()[0]
            mid=uuid.uuid4().hex;meta={**args['meta'],'external_receipt_key':key}
            import time
            c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(mid,tid,seq+1,'assistant',args['assistant'],time.time(),json.dumps(meta)));c.commit();return {'inserted':True,'message_id':mid}
        finally:c.close()


class Gateway:
    def __init__(self,path):
        self.thread_provider=ThreadProvider(path)
        self.control_provider=lambda op,args: {'mission_id':args.get('mission_id')} if op=='process' else {}
        self.operator_provider=lambda op,args: {}


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'threads.db';self.g=Gateway(self.path)
    def tearDown(self):self.tmp.cleanup()

    def test_default_is_local_and_browser_off(self):
        b=store._binding_get(self.g,'a'*32)
        self.assertEqual(b['channel'],'LOCAL');self.assertFalse(b['browser_transport']);self.assertIsNone(b['mission_id'])

    def test_mission_binding_is_persistent(self):
        b=store._binding_put(self.g,'a'*32,{'mission_id':'MISSION-1','channel':'LION_OPERATOR','target':'mission:MISSION-1'})
        self.assertTrue(b['persisted']);self.assertEqual(b['mission_id'],'MISSION-1');self.assertEqual(b['target'],'mission:MISSION-1');self.assertFalse(b['browser_transport'])
        self.assertEqual(store._binding_get(self.g,'a'*32)['channel'],'LION_OPERATOR')

    def test_lion_operator_requires_mission(self):
        with self.assertRaisesRegex(ValueError,'requires mission'):
            store._binding_put(self.g,'a'*32,{'mission_id':None,'channel':'LION_OPERATOR','target':None})

    def test_saas_is_explicit_browser_channel(self):
        b=store._binding_put(self.g,'a'*32,{'mission_id':None,'channel':'SAAS','target':None})
        self.assertTrue(b['browser_transport'])

    def test_target_cannot_cross_mission(self):
        with self.assertRaisesRegex(ValueError,'target mission mismatch'):
            store._binding_put(self.g,'a'*32,{'mission_id':'MISSION-1','channel':'LION_OPERATOR','target':'mission:MISSION-2'})

    def test_operator_request_is_idempotent_at_client_id(self):
        store._binding_put(self.g,'a'*32,{'mission_id':'MISSION-1','channel':'LION_OPERATOR','target':'mission:MISSION-1'})
        r1,dup1=store._begin_operator_request(self.g,'a'*32,'MISSION-1','mission:MISSION-1','b'*32,'hello')
        r2,dup2=store._begin_operator_request(self.g,'a'*32,'MISSION-1','mission:MISSION-1','b'*32,'hello')
        self.assertFalse(dup1);self.assertTrue(dup2);self.assertEqual(r1['command_id'],r2['command_id'])
        c=sqlite3.connect(self.path)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM messages').fetchone()[0],1)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM thread_operator_requests').fetchone()[0],1)
        c.close()

    def test_operator_poll_correlates_event_response_and_dedupes(self):
        store._binding_put(self.g,'a'*32,{'mission_id':'MISSION-1','channel':'LION_OPERATOR','target':'mission:MISSION-1'})
        store._begin_operator_request(self.g,'a'*32,'MISSION-1','mission:MISSION-1','c'*32,'hello')
        store._update_request(self.g,'c'*32,operator_message_id='opmsg-1',receipt_digest='d'*64,state='PERSISTED')
        def op_provider(op,args):
            if op=='state':
                return {'control':{'control_epoch':2,'control_owner':'AUTONOMOUS'},'messages':[{'message_id':'opmsg-1','kind':'MESSAGE','state':'APPLIED','applied_assignment_id':'assign-1'},{'message_id':'opreply-1','kind':'RESPONSE','content':'ack from mission','from_participant':'drone:LD001','applied_assignment_id':'assign-1'}],'message_deliveries':[{'message_id':'opmsg-1','recipient':'drone:LD001','delivery_state':'APPLIED'}]}
            if op=='events':return {'events':[{'event_type':'OPERATOR_MESSAGE_APPLIED','payload':{'message_ids':['opmsg-1'],'response_message_ids':['opreply-1']}}]}
            raise AssertionError(op)
        self.g.operator_provider=op_provider
        first=store._poll_operator(self.g,'session','a'*32)
        self.assertEqual(len(first['responses']),1);self.assertEqual(first['requests'][0]['state'],'COMPLETE')
        self.assertEqual(store._poll_operator(self.g,'session','a'*32)['responses'],[])
        c=sqlite3.connect(self.path);self.assertEqual(c.execute("SELECT COUNT(*) FROM messages WHERE role='assistant'").fetchone()[0],1);c.close()

    def test_same_client_id_different_text_is_rejected(self):
        store._binding_put(self.g,'a'*32,{'mission_id':'MISSION-1','channel':'LION_OPERATOR','target':'mission:MISSION-1'})
        store._begin_operator_request(self.g,'a'*32,'MISSION-1','mission:MISSION-1','b'*32,'hello')
        with self.assertRaisesRegex(ValueError,'conflict'):
            store._begin_operator_request(self.g,'a'*32,'MISSION-1','mission:MISSION-1','b'*32,'changed')


class UiPatchTests(unittest.TestCase):
    def test_ui_patch_makes_operator_bus_first_class_and_browser_explicit(self):
        mod=types.ModuleType('cyber_lion.app_coordination.local_intelligence_gateway')
        mod.UI="""AUTO · LOCAL-first<br><span id=\"sidebarSaas\" class=\"ok\">SaaS supervisor: sprawdzanie…</span><br><small id=\"sidebarSaasMeta\">Hybrid required · authority NONE</small>
<div class=\"k\">REMOTE COGNITIVE SUPERVISOR</div><h2>CHATGPT_SAAS_SUPERVISOR</h2><p class=\"status\">Brokered Firefox-project mediation · exact request tracking · authority NONE</p>
<div class=\"chat\"><div id=\"messages\" class=\"messages\">
<select id=\"composerRoute\" title=\"Kanał odpowiedzi\"><option value=\"AUTO\">Auto</option><option value=\"LOCAL\">LOCAL</option><option value=\"SAAS\">SAAS</option><option value=\"DUAL\">DUAL</option></select>
function addMsg(role,text){let d=document.createElement('div');d.className='msg '+role;patchHtml(d,'<div class=\"role\">'+(role==='user'?'TY':'LION')+'</div><div class=\"md\">'+md(text)+'</div>');messagesEl.appendChild(d);d.scrollIntoView({behavior:'smooth',block:'end'})}
threads=x.threads||[];patchHtml(threadListEl,
addMsg(m.role,m.content);history.push
qEl.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();go()}});async function boot()
"""
        class B:
            def do_GET(self):pass
            def do_POST(self):pass
            def do_DELETE(self):pass
        mod.make_handler=lambda g:B
        key='cyber_lion.app_coordination.local_intelligence_gateway';old=sys.modules.get(key);sys.modules[key]=mod
        import cyber_lion.app_coordination as package
        old_attr=getattr(package,'local_intelligence_gateway',None);package.local_intelligence_gateway=mod
        try:
            class G:
                def state(self):return {}
            ext.apply_operator_chat_extension(G)
            self.assertIn('LION / Operator Bus',mod.UI);self.assertIn('ChatGPT / Firefox',mod.UI)
            self.assertNotIn('<option value="AUTO">Auto</option>',mod.UI)
            self.assertIn('CHAT ↔ MISSION BINDING',mod.UI)
            self.assertIn("block:role==='assistant'?'start':'nearest'",mod.UI)
            self.assertIn("sort((a,b)=>(b.created_at||0)-(a.created_at||0))",mod.UI)
            self.assertIn('/operator-chat',mod.UI)
        finally:
            if old_attr is None:
                try:delattr(package,'local_intelligence_gateway')
                except AttributeError:pass
            else:package.local_intelligence_gateway=old_attr
            if old is None:sys.modules.pop(key,None)
            else:sys.modules[key]=old


if __name__=='__main__':unittest.main()
