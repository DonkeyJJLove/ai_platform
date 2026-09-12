from dataclasses import replace
from datetime import datetime,timezone
import unittest
from cyber_lion.contracts.failure_domain_evidence import HostBootObservation,FailureDomainContractError
from cyber_lion.enterprise.failure_domain_evidence import assess_failure_domains
D=lambda c:c*64
NOW=datetime(2026,9,12,11,0,10,tzinfo=timezone.utc)
B="58008236-23d6-48d9-a501-7e13b2b8c7b6"
def o(i,boot=B,time="2026-09-12T11:00:00+00:00"):return HostBootObservation(f"host-{i}",f"h{i}",boot,"WSL2",D(str(i)),time)
class FailureDomainTests(unittest.TestCase):
 def test_shared_boot_id_falsifies_kernel_domain_independence_only(self):
  a=assess_failure_domains((o(1),o(2),o(3),o(4)),trusted_now=NOW);self.assertEqual(a.kernel_boot_domain_independence,"FALSIFIED_SHARED_BOOT_ID");self.assertEqual(a.shared_boot_groups,(("host-1","host-2","host-3","host-4"),));self.assertEqual(a.physical_independence,"NOT_PROVEN");self.assertEqual(a.material_executor_independence,"NOT_PROVEN")
 def test_unique_boot_ids_do_not_promote_physical_independence(self):
  boots=("11111111-1111-1111-1111-111111111111","22222222-2222-2222-2222-222222222222")
  a=assess_failure_domains((o(1,boots[0]),o(2,boots[1])),trusted_now=NOW);self.assertEqual(a.kernel_boot_domain_independence,"NOT_FALSIFIED_BY_BOOT_ID");self.assertEqual(a.physical_independence,"NOT_PROVEN")
 def test_stale_evidence_is_unknown_not_pass(self):
  a=assess_failure_domains((o(1,time="2026-09-12T10:00:00+00:00"),o(2,time="2026-09-12T10:00:00+00:00")),trusted_now=NOW);self.assertEqual(a.currentness,"STALE");self.assertEqual(a.kernel_boot_domain_independence,"UNKNOWN_STALE_EVIDENCE")
 def test_duplicate_host_id_denied(self):
  with self.assertRaisesRegex(FailureDomainContractError,"duplicate host_id"):assess_failure_domains((o(1),replace(o(2),host_id="host-1")),trusted_now=NOW)
 def test_bad_boot_id_denied(self):
  with self.assertRaises(FailureDomainContractError):assess_failure_domains((o(1),replace(o(2),boot_id="same-host")),trusted_now=NOW)
 def test_material_independence_cannot_be_promoted_by_tamper(self):
  a=assess_failure_domains((o(1),o(2)),trusted_now=NOW)
  with self.assertRaisesRegex(FailureDomainContractError,"independence promotion"):replace(a,material_executor_independence="PROVEN").validate()
 def test_assessment_digest_is_deterministic_order_independent(self):
  a=assess_failure_domains((o(1),o(2),o(3)),trusted_now=NOW);b=assess_failure_domains((o(3),o(1),o(2)),trusted_now=NOW);self.assertEqual(a,b)
 def test_future_evidence_is_stale_unknown(self):
  a=assess_failure_domains((o(1,time="2026-09-12T11:01:00+00:00"),o(2,time="2026-09-12T11:01:00+00:00")),trusted_now=NOW);self.assertEqual(a.currentness,"STALE")
if __name__=='__main__':unittest.main()
