from dataclasses import replace
from pathlib import Path
import unittest

from cyber_lion.app_coordination.e02_app_session_provider_installation import (
    AppSessionAttesterInstallationCandidate,AppSessionAttesterInstallationError,
    DurableConsumptionProviderBinding,ExternalAttesterProviderDescriptor,
    apply_app_session_attester_installation,prepare_app_session_attester_installation,
)
D=lambda c:c*64
H=lambda c:c*40

def provider():return ExternalAttesterProviderDescriptor("provider-1","provider-instance-1",D("1"),"issuer-1",D("2"))
def durable():return DurableConsumptionProviderBinding("store-1",D("3"))
def candidate():return prepare_app_session_attester_installation(installation_id="e02-app-session-attester-r7",repository="DonkeyJJLove/ai_platform",source_head=H("4"),source_tree=H("5"),provider=provider(),durable_binding=durable(),trusted_time_provider_digest=D("6"))

class AppSessionAttesterInstallationTests(unittest.TestCase):
    def test_candidate_is_effect_free_uninstalled_and_digest_bound(self):
        c=candidate();self.assertEqual(c.state,"OFFLINE_CANDIDATE_NOT_INSTALLED");self.assertEqual(c.runtime_activation,"FORBIDDEN_BY_THIS_CANDIDATE");self.assertFalse(c.credential_material_present);self.assertEqual((c.authority_effect,c.runtime_effect),("NONE","NONE"));self.assertEqual(len(c.installation_digest),64)
    def test_provider_issuer_anchor_and_implementation_substitution_change_binding(self):
        base=candidate()
        variants=(replace(provider(),provider_id="other"),replace(provider(),provider_instance_id="other"),replace(provider(),provider_implementation_digest=D("f")),replace(provider(),issuer_id="other"),replace(provider(),trust_anchor_digest=D("e")))
        for p in variants:
            changed=prepare_app_session_attester_installation(installation_id=base.installation_id,repository=base.repository,source_head=base.source_head,source_tree=base.source_tree,provider=p,durable_binding=durable(),trusted_time_provider_digest=D("6"));self.assertNotEqual(changed.installation_digest,base.installation_digest)
    def test_store_source_and_trusted_time_substitution_change_binding(self):
        base=candidate()
        cases=(prepare_app_session_attester_installation(installation_id=base.installation_id,repository=base.repository,source_head=H("7"),source_tree=base.source_tree,provider=provider(),durable_binding=durable(),trusted_time_provider_digest=D("6")),prepare_app_session_attester_installation(installation_id=base.installation_id,repository=base.repository,source_head=base.source_head,source_tree=H("8"),provider=provider(),durable_binding=durable(),trusted_time_provider_digest=D("6")),prepare_app_session_attester_installation(installation_id=base.installation_id,repository=base.repository,source_head=base.source_head,source_tree=base.source_tree,provider=provider(),durable_binding=DurableConsumptionProviderBinding("other-store",D("9")),trusted_time_provider_digest=D("6")),prepare_app_session_attester_installation(installation_id=base.installation_id,repository=base.repository,source_head=base.source_head,source_tree=base.source_tree,provider=provider(),durable_binding=durable(),trusted_time_provider_digest=D("a")))
        for changed in cases:self.assertNotEqual(changed.installation_digest,base.installation_digest)
    def test_private_key_credential_and_effect_promotions_denied(self):
        with self.assertRaises(AppSessionAttesterInstallationError):replace(provider(),key_material_present=True).validate()
        with self.assertRaises(AppSessionAttesterInstallationError):replace(provider(),credential_mode="LION_STORED_SECRET").validate()
        with self.assertRaises(AppSessionAttesterInstallationError):replace(candidate(),credential_material_present=True).validate()
        with self.assertRaises(AppSessionAttesterInstallationError):replace(candidate(),runtime_effect="INSTALL").validate()
    def test_tamper_of_digest_state_or_activation_is_denied(self):
        c=candidate()
        for bad in (replace(c,installation_digest=D("f")),replace(c,state="INSTALLED"),replace(c,runtime_activation="ENABLED"),replace(c,installation_authority_requirement="NONE")):
            with self.assertRaises(AppSessionAttesterInstallationError):bad.validate()
    def test_apply_is_hard_fail_and_does_not_exist_as_hidden_installer(self):
        with self.assertRaisesRegex(AppSessionAttesterInstallationError,"separate current authority"):apply_app_session_attester_installation(candidate())
        src=Path('cyber_lion/app_coordination/e02_app_session_provider_installation.py').read_text();
        for forbidden in ('private_key','subprocess','urllib','socket','requests','systemctl','kubectl'):
            self.assertNotIn(forbidden,src)
    def test_exact_types_required(self):
        with self.assertRaises(AppSessionAttesterInstallationError):prepare_app_session_attester_installation(installation_id="x",repository="r",source_head=H("1"),source_tree=H("2"),provider=object(),durable_binding=durable(),trusted_time_provider_digest=D("3"))

if __name__=='__main__':unittest.main()
