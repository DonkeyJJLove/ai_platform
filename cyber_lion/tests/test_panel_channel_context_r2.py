from pathlib import Path
import unittest
from cyber_lion.app_coordination import hybrid_gateway_extension
from cyber_lion.app_coordination.saas_handoff_extension import ROUTE_CONTEXT,THREAD_CONTEXT,THREAD_BINDING_CONTEXT,apply_saas_handoff_extension
ROOT=Path(__file__).resolve().parents[2]

class PanelChannelContextR2Tests(unittest.TestCase):
 def test_firefox_mediator_is_explicit_opt_in(self):
  source=(ROOT/'tools'/'firefox_mediator'/'mediator.js').read_text()
  self.assertIn('relayEnabled=false',source);self.assertIn('async function tick(){if(!relayEnabled)return;await ensureDriver();',source)
  self.assertIn('/control/relay/on',source);self.assertIn('/control/relay/off',source)
 def test_ui_exposes_direct_provider_control_plane_and_explicit_binding(self):
  from cyber_lion.app_coordination import local_intelligence_gateway as gateway
  original=gateway.UI
  try:
   hybrid_gateway_extension._patch_ui();ui=gateway.UI
   self.assertIn('SAAS_DIRECT · OpenAI Responses',ui);self.assertIn('LEGACY_BROWSER · manual Firefox',ui)
   self.assertIn('CONTROL SentinelX',ui);self.assertNotIn('SAAS · SentinelX default',ui)
   self.assertIn('remote-model ',ui);self.assertIn("owner=operatorProjection?.control?.control_owner||'UNKNOWN'",ui)
   self.assertIn("pair=operatorSessionPaired?'PAIRED':'UNPAIRED'",ui);self.assertIn('const threadRemoteState=new Map()',ui)
   self.assertIn('hydrateThreadRemoteState(x.messages||[],id)',ui);self.assertIn("request_state:'DELIVERED'",ui)
   self.assertIn('receipt=remote.receipt_digest?',ui);self.assertIn('threadRemoteState.delete(id);activeThreadId=null;activeThreadContext=null',ui)
   self.assertIn('Bind mission',ui);self.assertIn('Unbind',ui);self.assertIn('persistThreadContext',ui)
   self.assertIn("mission=bound.mission_id||'UNBOUND'",ui);self.assertNotIn("bound.mission_id||missionFocusId",ui)
   self.assertIn('activeThreadContext=x',ui);self.assertIn("block:role==='assistant'?'start':'end'",ui)
   self.assertIn('addMsg(m.role,m.content,{scroll:false})',ui);self.assertIn('UNPAIRED · CONTROLS DISABLED',ui)
  finally:gateway.UI=original
 def _dummy(self):
  class Dummy:
   def __init__(self):self.calls=[];self.control_provider=self.control
   def _route(self,m):return ('MODEL_ONLY','base')
   def state(self):return {}
   def chat(self,message,use_web=False,history=None,output_language='auto'):return {'route':'MODEL_ONLY','answer':'LOCAL:'+message,'tool_calls':[],'material_receipts':[]}
   def control(self,op,args):
    self.calls.append((op,args))
    if op=='process':return {'mission_id':'M1','state':'RUNNING','process':{'current_phase':'P1'}}
    if op=='saas_request':return {'request_code':'ABCD1234','request_id':'saas-'+'1'*32,'transport':'OPENAI_RESPONSES_API_MEDIATED','inference_transport':'OPENAI_RESPONSES_API_MEDIATED','control_transport':'SENTINELX_OPERATOR_CONTROL','provider':'OPENAI','authority_effect':'NONE'}
    if op=='saas_status':return {'state':'UNBOUND'}
    raise AssertionError((op,args))
  apply_saas_handoff_extension(Dummy);return Dummy()
 def test_explicit_local_cannot_be_upgraded_to_dual(self):
  d=self._dummy();rt=ROUTE_CONTEXT.set('LOCAL')
  try:out=d.chat('Porównaj SaaS i model lokalny: tylko lokalnie',output_language='pl')
  finally:ROUTE_CONTEXT.reset(rt)
  self.assertNotIn('saas_handoff',out);self.assertEqual(out['thread_context']['composer_route'],'LOCAL')
 def test_persisted_thread_binding_drives_saas_not_global_focus(self):
  d=self._dummy();tt=THREAD_CONTEXT.set('a'*32);rt=ROUTE_CONTEXT.set('SAAS_DIRECT');bt=THREAD_BINDING_CONTEXT.set({'mission_id':'M1','mission_phase_snapshot':'P1','channel':'SAAS_DIRECT','provider':'OPENAI','binding_revision':4,'binding_state':'MISSION_BOUND'})
  try:out=d.chat('status',output_language='pl')
  finally:THREAD_CONTEXT.reset(tt);ROUTE_CONTEXT.reset(rt);THREAD_BINDING_CONTEXT.reset(bt)
  req=[a for op,a in d.calls if op=='saas_request'];self.assertEqual(len(req),1)
  self.assertEqual(req[0]['thread_id'],'a'*32);self.assertEqual(req[0]['mission_id'],'M1');self.assertEqual(req[0]['control_transport'],'SENTINELX_OPERATOR_CONTROL');self.assertEqual(req[0]['inference_transport'],'OPENAI_RESPONSES_API_MEDIATED');self.assertEqual(req[0]['provider'],'OPENAI')
  self.assertEqual(out['thread_context']['binding_state'],'MISSION_BOUND');self.assertEqual(out['thread_context']['mission_id'],'M1')
  self.assertFalse(any(op=='recent' for op,_ in d.calls));self.assertFalse(any(op=='post_message' for op,_ in d.calls))
 def test_unbound_dual_never_inherits_global_mission_focus(self):
  d=self._dummy();rt=ROUTE_CONTEXT.set('DUAL');bt=THREAD_BINDING_CONTEXT.set({'mission_id':None,'channel':'DUAL','binding_state':'MISSION_UNBOUND'})
  try:out=d.chat('compare',output_language='pl')
  finally:ROUTE_CONTEXT.reset(rt);THREAD_BINDING_CONTEXT.reset(bt)
  req=[a for op,a in d.calls if op=='saas_request'];self.assertEqual(len(req),1);self.assertEqual(req[0]['scope_type'],'CONTROL_PLANE');self.assertNotIn('mission_id',req[0]);self.assertNotIn('thread_id',req[0]);self.assertIsNone(out['thread_context']['mission_id'])
 def test_bound_phase_drift_is_visible_without_rebinding_mission(self):
  d=self._dummy();tt=THREAD_CONTEXT.set('b'*32);rt=ROUTE_CONTEXT.set('LOCAL');bt=THREAD_BINDING_CONTEXT.set({'mission_id':'M1','mission_phase_snapshot':'OLD','channel':'LOCAL','provider':None,'binding_revision':2,'binding_state':'MISSION_BOUND'})
  try:out=d.chat('local',output_language='pl')
  finally:THREAD_CONTEXT.reset(tt);ROUTE_CONTEXT.reset(rt);THREAD_BINDING_CONTEXT.reset(bt)
  self.assertEqual(out['thread_context']['mission_id'],'M1');self.assertEqual(out['thread_context']['current_phase'],'P1');self.assertEqual(out['thread_context']['binding_state'],'MISSION_BINDING_STALE')
if __name__=='__main__':unittest.main()
