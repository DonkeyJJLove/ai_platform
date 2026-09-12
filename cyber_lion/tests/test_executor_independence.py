from dataclasses import replace
from datetime import datetime,timezone
import unittest
from cyber_lion.contracts.executor_independence import *
from cyber_lion.enterprise.executor_independence import assess_executor_independence
D=lambda c:c*64
NOW=datetime(2026,9,12,14,0,10,tzinfo=timezone.utc)
OBS='2026-09-12T14:00:00+00:00';EXP='2026-09-12T14:01:00+00:00';BOOT='58008236-23d6-48d9-a501-7e13b2b8c7b6'
def o(i,boot=BOOT,time=OBS):return ConnectorExecutorObservation(f'connector-{i}',f'host-{i}',f'h{i}',boot,'WSL2',D(str(i)),time)
def a(i,physical=None,control=None,runtime=None,anchor=None,virt='BARE_METAL',time=OBS):return IndependentExecutorAttestation(f'exec-{i}',runtime or f'rt-{i}',physical or f'physical-{i}',control or f'control-{i}',virt,D('a'),D('b'),D('c'),anchor or D(str(i)),f'issuer-{i}',time,EXP)
class ExecutorIndependenceTests(unittest.TestCase):
 def test_four_connectors_shared_boot_falsifies_boot_but_not_material_executor(self):
  x=assess_executor_independence((o(1),o(2),o(3),o(4)),trusted_now=NOW);self.assertEqual(x.connector_count,4);self.assertEqual(x.routing_identity,'DISTINCT_CONNECTOR_IDENTITIES_OBSERVED');self.assertEqual(x.boot_domain_independence,'FALSIFIED_SHARED_BOOT_ID');self.assertEqual(x.material_executor_independence,'NOT_PROVEN');self.assertEqual(x.attested_executor_count,0)
 def test_distinct_boot_ids_still_do_not_prove_material_independence(self):
  boots=('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222');x=assess_executor_independence((o(1,boots[0]),o(2,boots[1])),trusted_now=NOW);self.assertEqual(x.boot_domain_independence,'NOT_FALSIFIED_BY_BOOT_ID');self.assertEqual(x.material_executor_independence,'NOT_PROVEN')
 def test_external_attested_distinct_domains_can_only_form_candidate(self):
  boots=('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222');x=assess_executor_independence((o(1,boots[0]),o(2,boots[1])),attestations=(a(1),a(2)),trusted_now=NOW);self.assertEqual(x.runtime_instance_independence,'ATTESTED_DISTINCT');self.assertEqual(x.physical_machine_independence,'ATTESTED_DISTINCT');self.assertEqual(x.control_domain_independence,'ATTESTED_DISTINCT');self.assertEqual(x.material_executor_independence,'ATTESTED_DISTINCT_CANDIDATE');self.assertEqual((x.authority_effect,x.runtime_effect),('NONE','NONE'))
 def test_same_control_anchor_cannot_prove_control_independence(self):
  boots=('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222');x=assess_executor_independence((o(1,boots[0]),o(2,boots[1])),attestations=(a(1,anchor=D('9')),a(2,anchor=D('9'))),trusted_now=NOW);self.assertEqual(x.control_domain_independence,'NOT_PROVEN');self.assertEqual(x.material_executor_independence,'NOT_PROVEN')
 def test_same_physical_domain_blocks_material_independence(self):
  boots=('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222');x=assess_executor_independence((o(1,boots[0]),o(2,boots[1])),attestations=(a(1,physical='same'),a(2,physical='same')),trusted_now=NOW);self.assertEqual(x.physical_machine_independence,'NOT_PROVEN');self.assertEqual(x.material_executor_independence,'NOT_PROVEN')
 def test_virtualized_attestation_cannot_prove_physical_independence(self):
  with self.assertRaisesRegex(ExecutorIndependenceError,'virtualization class'):a(1,virt='WSL2').validate()
 def test_shared_boot_cannot_be_overridden_by_attestations(self):
  x=assess_executor_independence((o(1),o(2)),attestations=(a(1),a(2)),trusted_now=NOW);self.assertEqual(x.boot_domain_independence,'FALSIFIED_SHARED_BOOT_ID');self.assertEqual(x.material_executor_independence,'NOT_PROVEN')
 def test_stale_evidence_yields_unknown_not_pass(self):
  x=assess_executor_independence((o(1,time='2026-09-12T13:00:00+00:00'),o(2,time='2026-09-12T13:00:00+00:00')),trusted_now=NOW);self.assertEqual(x.currentness,'STALE');self.assertEqual(x.material_executor_independence,'UNKNOWN_STALE_EVIDENCE')
 def test_duplicate_connector_or_host_is_not_distinct_identity(self):
  x=assess_executor_independence((o(1),replace(o(2),connector_id='connector-1')),trusted_now=NOW);self.assertEqual(x.routing_identity,'DUPLICATE_CONNECTOR_OR_HOST_IDENTITY');self.assertEqual(x.material_executor_independence,'NOT_PROVEN')
 def test_tamper_cannot_promote_material_state(self):
  x=assess_executor_independence((o(1),o(2)),trusted_now=NOW)
  with self.assertRaises(ExecutorIndependenceError):replace(x,material_executor_independence='ATTESTED_DISTINCT_CANDIDATE').validate()
 def test_order_independent(self):
  x=assess_executor_independence((o(1),o(2),o(3)),trusted_now=NOW);y=assess_executor_independence((o(3),o(1),o(2)),trusted_now=NOW);self.assertEqual(x,y)
if __name__=='__main__':unittest.main()
