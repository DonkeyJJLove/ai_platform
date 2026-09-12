"""Effect-free installation contract for an external E02 APP_SESSION attester.

The contract binds identities required to install an external verifier around the
already-existing APP_SESSION verification and durable-consumption candidates. It
contains no credential, private key, network client, process launcher or activation
primitive. Installation and runtime activation remain separate authority effects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

from cyber_lion.app_coordination.source_candidates import digest, text

DOMAIN=b"LION/E02/APP-SESSION-ATTESTER-INSTALLATION/1\0"
SHA40=re.compile(r"^[0-9a-f]{40}$")

class AppSessionAttesterInstallationError(ValueError): pass

def _sha40(value,label):
    if type(value) is not str or SHA40.fullmatch(value) is None:raise AppSessionAttesterInstallationError(label)
    return value

def _canon(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

@dataclass(frozen=True)
class ExternalAttesterProviderDescriptor:
    provider_id:str
    provider_instance_id:str
    provider_implementation_digest:str
    issuer_id:str
    trust_anchor_digest:str
    verifier_protocol:str="EXTERNAL_APP_SESSION_VERIFIER_V1"
    credential_mode:str="EXTERNAL_NOT_STORED_IN_LION"
    key_material_present:bool=False
    authority_effect:str="NONE"
    runtime_effect:str="NONE"
    def validate(self):
        for v in (self.provider_id,self.provider_instance_id,self.issuer_id,self.verifier_protocol,self.credential_mode):text(v)
        for v in (self.provider_implementation_digest,self.trust_anchor_digest):digest(v)
        if self.verifier_protocol!="EXTERNAL_APP_SESSION_VERIFIER_V1":raise AppSessionAttesterInstallationError("verifier protocol")
        if self.credential_mode!="EXTERNAL_NOT_STORED_IN_LION" or self.key_material_present is not False:raise AppSessionAttesterInstallationError("credential/private-key promotion")
        if self.authority_effect!="NONE" or self.runtime_effect!="NONE":raise AppSessionAttesterInstallationError("provider effect promotion")
        return self
    def descriptor_digest(self):self.validate();return sha256(DOMAIN+b"PROVIDER\0"+_canon(asdict(self))).hexdigest()

@dataclass(frozen=True)
class DurableConsumptionProviderBinding:
    store_id:str
    store_identity_digest:str
    state_schema:str="LION_E02_APP_SESSION_DURABLE_CANDIDATE_V1"
    persistence_class:str="LOCAL_DURABLE_CANDIDATE"
    authority_effect:str="NONE"
    runtime_effect:str="NONE"
    def validate(self):
        text(self.store_id);digest(self.store_identity_digest);text(self.state_schema);text(self.persistence_class)
        if self.state_schema!="LION_E02_APP_SESSION_DURABLE_CANDIDATE_V1" or self.persistence_class!="LOCAL_DURABLE_CANDIDATE":raise AppSessionAttesterInstallationError("durable store class")
        if self.authority_effect!="NONE" or self.runtime_effect!="NONE":raise AppSessionAttesterInstallationError("durable binding effect promotion")
        return self
    def binding_digest(self):self.validate();return sha256(DOMAIN+b"DURABLE\0"+_canon(asdict(self))).hexdigest()

@dataclass(frozen=True)
class AppSessionAttesterInstallationCandidate:
    installation_id:str
    repository:str
    source_head:str
    source_tree:str
    provider_descriptor_digest:str
    durable_binding_digest:str
    trusted_time_provider_digest:str
    expected_issuer_id:str
    expected_trust_anchor_digest:str
    configuration_digest:str
    installation_digest:str
    state:str="OFFLINE_CANDIDATE_NOT_INSTALLED"
    installation_authority_requirement:str="SEPARATE_CURRENT_INSTALLATION_AUTHORITY_REQUIRED"
    runtime_activation:str="FORBIDDEN_BY_THIS_CANDIDATE"
    credential_material_present:bool=False
    authority_effect:str="NONE"
    runtime_effect:str="NONE"
    def validate(self):
        for v in (self.installation_id,self.repository,self.expected_issuer_id,self.state,self.installation_authority_requirement,self.runtime_activation):text(v)
        _sha40(self.source_head,"source head");_sha40(self.source_tree,"source tree")
        for v in (self.provider_descriptor_digest,self.durable_binding_digest,self.trusted_time_provider_digest,self.expected_trust_anchor_digest,self.configuration_digest,self.installation_digest):digest(v)
        if self.state!="OFFLINE_CANDIDATE_NOT_INSTALLED" or self.installation_authority_requirement!="SEPARATE_CURRENT_INSTALLATION_AUTHORITY_REQUIRED":raise AppSessionAttesterInstallationError("installation state/authority promotion")
        if self.runtime_activation!="FORBIDDEN_BY_THIS_CANDIDATE" or self.credential_material_present is not False:raise AppSessionAttesterInstallationError("activation/credential promotion")
        if self.authority_effect!="NONE" or self.runtime_effect!="NONE":raise AppSessionAttesterInstallationError("installation effect promotion")
        body={k:v for k,v in asdict(self).items() if k!="installation_digest"}
        if self.installation_digest!=sha256(DOMAIN+b"INSTALL\0"+_canon(body)).hexdigest():raise AppSessionAttesterInstallationError("installation digest mismatch")
        return self

def prepare_app_session_attester_installation(*,installation_id,repository,source_head,source_tree,provider,durable_binding,trusted_time_provider_digest):
    if type(provider) is not ExternalAttesterProviderDescriptor or type(durable_binding) is not DurableConsumptionProviderBinding:raise AppSessionAttesterInstallationError("exact provider/binding types required")
    provider.validate();durable_binding.validate();text(installation_id);text(repository);_sha40(source_head,"source head");_sha40(source_tree,"source tree");digest(trusted_time_provider_digest)
    config={"provider":provider.descriptor_digest(),"durable":durable_binding.binding_digest(),"trusted_time_provider":trusted_time_provider_digest,"issuer":provider.issuer_id,"trust_anchor":provider.trust_anchor_digest,"source_head":source_head,"source_tree":source_tree}
    config_digest=sha256(DOMAIN+b"CONFIG\0"+_canon(config)).hexdigest()
    fields=dict(installation_id=installation_id,repository=repository,source_head=source_head,source_tree=source_tree,provider_descriptor_digest=provider.descriptor_digest(),durable_binding_digest=durable_binding.binding_digest(),trusted_time_provider_digest=trusted_time_provider_digest,expected_issuer_id=provider.issuer_id,expected_trust_anchor_digest=provider.trust_anchor_digest,configuration_digest=config_digest,state="OFFLINE_CANDIDATE_NOT_INSTALLED",installation_authority_requirement="SEPARATE_CURRENT_INSTALLATION_AUTHORITY_REQUIRED",runtime_activation="FORBIDDEN_BY_THIS_CANDIDATE",credential_material_present=False,authority_effect="NONE",runtime_effect="NONE")
    fields["installation_digest"]=sha256(DOMAIN+b"INSTALL\0"+_canon(fields)).hexdigest()
    return AppSessionAttesterInstallationCandidate(**fields).validate()

def apply_app_session_attester_installation(*args,**kwargs):
    raise AppSessionAttesterInstallationError("external attester installation requires separate current authority and external installer")
