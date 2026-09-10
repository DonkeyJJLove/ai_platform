import unittest
from tools.vkt_r3_validate_600s import check_snapshot,run_validation,PHASES,EXPECTED_FRESH
class Fake:
 def __init__(self,states):self.states=list(states);self.i=0
 def read(self):
  x=self.states[min(self.i,len(self.states)-1)];self.i+=1;return x

def good(uid='a'*64):
 return {'materialized':384,'ready':384,'restart_count_total':0,'unique_uid_count':384,'pod_uid_set_sha256':uid,'vendor_requests':0,'by_fleet':{},'router_state':{'fresh_count':384,'fresh_by_fleet':EXPECTED_FRESH,'messages_total':768,'ack_count':768,'ack_rate':1.0,'duplicates':0,'orphans':0,'cases_total':36,'cases_seen':36,'cases_proven':36,'participants':{p:128 for p in PHASES},'mission':{'completed':True}}}
class Clock:
 def __init__(self):self.t=0.0
 def now(self):return self.t
 def sleep(self,x):self.t+=x
class T(unittest.TestCase):
 def test_good_snapshot(self):self.assertEqual(check_snapshot(__import__('cyber_lion.vkt_r3.mission_control.models',fromlist=['normalize']).normalize(good()),'a'*64),[])
 def test_uid_drift_fails(self):
  c=Clock();r=run_validation(Fake([good(),good('b'*64)]),duration=10,interval=5,now=c.now,sleep=c.sleep);self.assertEqual(r['status'],'FAIL');self.assertIn('UID_SET_DRIFT',r['samples'][-1]['errors'])
 def test_pass(self):
  c=Clock();r=run_validation(Fake([good(),good(),good(),good()]),duration=10,interval=5,now=c.now,sleep=c.sleep);self.assertEqual(r['status'],'PASS')
 def test_orphan_fails_preflight(self):
  x=good();x['router_state']['orphans']=1;c=Clock();r=run_validation(Fake([x]),duration=10,interval=5,now=c.now,sleep=c.sleep);self.assertEqual(r['status'],'DEFERRED')
if __name__=='__main__':unittest.main()
