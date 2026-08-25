"""Fail-closed non-effectful builder-entry permit issuer."""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from cyber_lion.contracts.builder_entry_permit import (
    BUILDER_CAPABILITY_CLASS, SCHEMA_VERSION, BuilderEntryPermit, TrustedBuilderSubject,
    compute_builder_entry_replay_digest,
)
from cyber_lion.contracts.build_authorization_consumption import BuildAuthorizationConsumptionPermit
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.candidate_build_authorization import LiveAdmittedResourceAuthority, LiveResourceAuthorityAdmission

class BuilderEntryPermitError(RuntimeError): pass

_EFFECT_METHODS=frozenset({"execute","write","push","merge","deploy","release","create_branch","create_pr","run_test","build_candidate","consume_candidate","start_builder","issue_grant"})

def _utc(v:str,n:str)->datetime:
    try: x=datetime.fromisoformat(v.replace("Z","+00:00"))
    except (AttributeError,ValueError) as e: raise BuilderEntryPermitError(f"{n} invalid") from e
    if x.tzinfo is None: raise BuilderEntryPermitError(f"{n} must be timezone-aware")
    return x.astimezone(timezone.utc)

class TrustedRepositoryBaselineSource(Protocol):
    def current(self,repository:str)->TrustedRepositoryBaseline: ...
class F005StateSource(Protocol):
    def current(self)->Mapping[str,Any]: ...
class BuilderEntryReplayGuard(Protocol):
    def consume(self,replay_digest:str,*,consumed_at:str)->bool: ...

class PersistentBuilderEntryReplayGuard:
    DOMAIN="candidate-builder-entry-consumption"
    def __init__(self,store:object):
        if not callable(getattr(store,"consume_replay",None)): raise BuilderEntryPermitError("persistent replay store unavailable")
        self._store=store
    def consume(self,replay_digest:str,*,consumed_at:str)->bool:
        return self._store.consume_replay(self.DOMAIN,replay_digest,consumed_at)

class TrustedBuilderSubjectSource(ABC):
    source_kind="trusted-control-plane"
    @abstractmethod
    def _lookup_exact(self,*,builder_subject_id:str,builder_instance_id:str,repository:str,candidate_scope:tuple[str,...],resource_scope:tuple[str,...])->tuple[TrustedBuilderSubject,...]: raise NotImplementedError
    def resolve_exact(self,*,builder_subject_id:str,builder_instance_id:str,repository:str,candidate_scope:tuple[str,...],resource_scope:tuple[str,...])->TrustedBuilderSubject:
        if getattr(self,"source_kind",None)!="trusted-control-plane": raise BuilderEntryPermitError("untrusted builder source")
        records=self._lookup_exact(builder_subject_id=builder_subject_id,builder_instance_id=builder_instance_id,repository=repository,candidate_scope=candidate_scope,resource_scope=resource_scope)
        if type(records) is not tuple: raise BuilderEntryPermitError("builder source result must be tuple")
        if len(records)==0: raise BuilderEntryPermitError("trusted builder subject not found")
        if len(records)>1: raise BuilderEntryPermitError("trusted builder subject lookup ambiguous")
        s=records[0]
        if type(s) is not TrustedBuilderSubject: raise BuilderEntryPermitError("trusted builder subject type invalid")
        try: s.validate()
        except Exception as e: raise BuilderEntryPermitError("trusted builder subject invalid") from e
        if not s.subject_digest or s.subject_digest!=s.compute_digest(): raise BuilderEntryPermitError("trusted builder subject must be sealed")
        expected=(builder_subject_id,builder_instance_id,repository,candidate_scope,resource_scope,BUILDER_CAPABILITY_CLASS)
        actual=(s.builder_subject_id,s.builder_instance_id,s.repository,s.candidate_scope,s.resource_scope,s.capability_class)
        if actual!=expected: raise BuilderEntryPermitError("builder subject binding mismatch")
        return s

class BuilderEntryPermitEngine:
    """Issue one entry permit; never consume it or start a builder."""
    def __init__(self,*,live_authority:LiveResourceAuthorityAdmission,baseline_source:TrustedRepositoryBaselineSource,f005_state_source:F005StateSource,builder_source:TrustedBuilderSubjectSource,replay_guard:BuilderEntryReplayGuard):
        if type(live_authority) is not LiveResourceAuthorityAdmission: raise BuilderEntryPermitError("live authority admission required")
        if not isinstance(builder_source,TrustedBuilderSubjectSource): raise BuilderEntryPermitError("exact trusted builder source boundary required")
        if getattr(builder_source,"source_kind",None)!="trusted-control-plane": raise BuilderEntryPermitError("untrusted builder source")
        if type(builder_source).resolve_exact is not TrustedBuilderSubjectSource.resolve_exact: raise BuilderEntryPermitError("trusted builder resolver override denied")
        for o,m in ((baseline_source,"current"),(f005_state_source,"current"),(replay_guard,"consume")):
            if not callable(getattr(o,m,None)): raise BuilderEntryPermitError("builder entry dependency unavailable")
        self._live=live_authority; self._baseline=baseline_source; self._f005=f005_state_source; self._builders=builder_source; self._replay=replay_guard

    @staticmethod
    def _permit(v:object)->BuildAuthorizationConsumptionPermit:
        if type(v) is not BuildAuthorizationConsumptionPermit: raise BuilderEntryPermitError("exact consumption permit required")
        try: v.validate()
        except Exception as e: raise BuilderEntryPermitError("consumption permit invalid") from e
        if not v.consumption_permit_digest or v.consumption_permit_digest!=v.compute_digest(): raise BuilderEntryPermitError("consumption permit must be sealed")
        if v.consumption_replay_digest!=v.compute_consumption_replay_digest(): raise BuilderEntryPermitError("source replay binding invalid")
        if v.state!="CONSUMPTION_PERMIT_ISSUED" or v.action!="BUILD_CANDIDATE": raise BuilderEntryPermitError("source permit state/action invalid")
        return v

    @staticmethod
    def _live_receipt(v:object)->LiveAdmittedResourceAuthority:
        if type(v) is not LiveAdmittedResourceAuthority: raise BuilderEntryPermitError("exact live authority receipt required")
        try: v.validate()
        except Exception as e: raise BuilderEntryPermitError("live authority receipt invalid") from e
        return v

    @staticmethod
    def _f005_ok(v:Mapping[str,Any])->None:
        if not isinstance(v,Mapping) or v.get("state")!="QUARANTINED" or v.get("effect_authority")!="DENY": raise BuilderEntryPermitError("F005 quarantine invariant failed")

    @staticmethod
    def _trusted_subject(v:object,*,builder_subject_id:str,builder_instance_id:str,repository:str,candidate_scope:tuple[str,...],resource_scope:tuple[str,...])->TrustedBuilderSubject:
        if type(v) is not TrustedBuilderSubject: raise BuilderEntryPermitError("trusted builder subject type invalid")
        try: v.validate()
        except Exception as e: raise BuilderEntryPermitError("trusted builder subject invalid") from e
        if not v.subject_digest or v.subject_digest!=v.compute_digest(): raise BuilderEntryPermitError("trusted builder subject must be sealed")
        expected=(builder_subject_id,builder_instance_id,repository,candidate_scope,resource_scope,BUILDER_CAPABILITY_CLASS,"ADMITTED","trusted-control-plane")
        actual=(v.builder_subject_id,v.builder_instance_id,v.repository,v.candidate_scope,v.resource_scope,v.capability_class,v.state,v.source_kind)
        if actual!=expected: raise BuilderEntryPermitError("trusted builder subject request binding mismatch")
        return v

    def issue_permit(self,*,source_permit:BuildAuthorizationConsumptionPermit,admitted_authority:LiveAdmittedResourceAuthority,builder_subject_id:str,builder_instance_id:str,trusted_now:datetime)->BuilderEntryPermit:
        p=self._permit(source_permit); admitted=self._live_receipt(admitted_authority)
        if not isinstance(trusted_now,datetime) or trusted_now.tzinfo is None: raise BuilderEntryPermitError("trusted_now must be timezone-aware")
        now=trusted_now.astimezone(timezone.utc)
        if now < _utc(p.authorization_valid_from,"authorization valid_from") or now >= _utc(p.authorization_expires_at,"authorization expires_at"): raise BuilderEntryPermitError("source authorization outside validity window")

        current=self._baseline.current(p.repository)
        if type(current) is not TrustedRepositoryBaseline: raise BuilderEntryPermitError("trusted baseline type invalid")
        current.validate()
        if (current.repository,current.master_sha,current.master_tree_sha)!=(p.repository,p.baseline_master_sha,p.baseline_master_tree_sha): raise BuilderEntryPermitError("builder-entry baseline stale")

        try: authority=self._live.revalidate(admitted,now=now)
        except Exception as e: raise BuilderEntryPermitError("current authority revalidation failed") from e
        if type(authority) is not LiveAdmittedResourceAuthority: raise BuilderEntryPermitError("revalidated authority type invalid")
        authority.validate()
        expected=(p.repository,p.grant_id,p.leaf_grant_digest,p.authority_lineage_digest,p.authority_provenance_id,p.authority_epoch,p.authority_state_version,p.root_grant_id,p.root_grant_digest,p.current_authority_digest,p.resource_scope,"BUILD_CANDIDATE")
        actual=(authority.repository,authority.grant_id,authority.leaf_grant_digest,authority.lineage_digest,authority.provenance_id,authority.epoch,authority.epoch_state_version,authority.root_grant_id,authority.root_grant_digest,authority.digest(),authority.resource_scope,authority.action)
        if actual!=expected: raise BuilderEntryPermitError("source permit/current authority mismatch")

        self._f005_ok(self._f005.current())
        subject=self._builders.resolve_exact(builder_subject_id=builder_subject_id,builder_instance_id=builder_instance_id,repository=p.repository,candidate_scope=p.candidate_scope,resource_scope=p.resource_scope)
        subject=self._trusted_subject(subject,builder_subject_id=builder_subject_id,builder_instance_id=builder_instance_id,repository=p.repository,candidate_scope=p.candidate_scope,resource_scope=p.resource_scope)
        if now < _utc(subject.valid_from,"builder valid_from") or now >= _utc(subject.expires_at,"builder expires_at"): raise BuilderEntryPermitError("builder subject outside validity window")

        current_baseline_digest=current.digest(); current_authority_digest=authority.digest()
        kwargs=dict(source_consumption_permit_id=p.consumption_permit_id,source_consumption_permit_digest=p.consumption_permit_digest,source_consumption_replay_digest=p.consumption_replay_digest,repository=p.repository,baseline_master_sha=p.baseline_master_sha,baseline_master_tree_sha=p.baseline_master_tree_sha,current_baseline_digest=current_baseline_digest,action="BUILD_CANDIDATE",candidate_scope=p.candidate_scope,resource_scope=p.resource_scope,authority_epoch=p.authority_epoch,authority_state_version=p.authority_state_version,root_grant_id=p.root_grant_id,root_grant_digest=p.root_grant_digest,current_authority_digest=current_authority_digest,builder_subject_id=subject.builder_subject_id,builder_instance_id=subject.builder_instance_id,builder_capability_class=subject.capability_class,builder_identity_digest=subject.identity_digest,builder_implementation_digest=subject.implementation_digest,builder_attestation_digest=subject.attestation_digest)
        replay=compute_builder_entry_replay_digest(**kwargs); checked_at=now.isoformat()
        if self._replay.consume(replay,consumed_at=checked_at) is not True: raise BuilderEntryPermitError("builder entry replay denied")
        return BuilderEntryPermit(schema_version=SCHEMA_VERSION,builder_entry_permit_id=f"bep:{replay}",checked_at=checked_at,builder_entry_replay_digest=replay,**kwargs).sealed()

    @classmethod
    def assert_no_effect_surface(cls)->None:
        for name in _EFFECT_METHODS:
            if hasattr(cls,name): raise BuilderEntryPermitError(f"effect surface present: {name}")
