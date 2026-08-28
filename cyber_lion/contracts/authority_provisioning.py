"""Contracts for externally administered merge-authority provisioning."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json,re

MERGE_ACTION="merge_pull_request"
MERGE_METHODS=frozenset({"merge","squash","rebase"})
_SHA=re.compile(r"^[0-9a-f]{40}$"); _HEX=re.compile(r"^[0-9a-f]{64}$")

class AuthorityProvisioningContractError(ValueError): pass

def _txt(v,n,limit=512):
    if not isinstance(v,str) or not v.strip() or len(v)>limit or "\x00" in v: raise AuthorityProvisioningContractError(f"{n} invalid")
    return v
def _sha(v,n):
    if not isinstance(v,str) or not _SHA.fullmatch(v): raise AuthorityProvisioningContractError(f"{n} invalid")
def _hex(v,n):
    if not isinstance(v,str) or not _HEX.fullmatch(v): raise AuthorityProvisioningContractError(f"{n} invalid")
def _time(v,n):
    _txt(v,n,128)
    try: x=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e: raise AuthorityProvisioningContractError(f"{n} invalid") from e
    if x.tzinfo is None: raise AuthorityProvisioningContractError(f"{n} invalid")
    return x
def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _digest(domain,obj): return sha256(domain+_canon(obj)).hexdigest()
def _unsigned(obj):
    d=asdict(obj); d.pop("signature",None); return d

@dataclass(frozen=True)
class AuthorityProvisioningRequest:
    request_id:str; repository:str; pr_number:int; base_sha:str; head_sha:str; mission_id:str; action:str; merge_method:str; policy_digest:str; requester_subject_id:str; effect_executor_subject_id:str; requested_at:str
    def validate(self):
        for n in ("request_id","repository","mission_id","requester_subject_id","effect_executor_subject_id"): _txt(getattr(self,n),n)
        if type(self.pr_number) is not int or self.pr_number<=0: raise AuthorityProvisioningContractError("pr_number invalid")
        _sha(self.base_sha,"base_sha"); _sha(self.head_sha,"head_sha")
        if self.action!=MERGE_ACTION or self.merge_method not in MERGE_METHODS: raise AuthorityProvisioningContractError("merge request invalid")
        if not self.policy_digest.startswith("sha256:") or not _HEX.fullmatch(self.policy_digest[7:]): raise AuthorityProvisioningContractError("policy_digest invalid")
        if self.requester_subject_id==self.effect_executor_subject_id: raise AuthorityProvisioningContractError("requester/executor separation required")
        _time(self.requested_at,"requested_at"); return self
    def digest(self): self.validate(); return _digest(b"LION/AUTHORITY-PROVISIONING-REQUEST/1\0",asdict(self))

@dataclass(frozen=True)
class AuthorityIssuerBinding:
    subject_id:str; trust_domain:str; key_id:str; algorithm:str; role:str; provenance_id:str
    def validate(self):
        for n in ("subject_id","trust_domain","key_id","algorithm","provenance_id"): _txt(getattr(self,n),n)
        if self.role not in {"provisioning-administrator","authority-issuer"}: raise AuthorityProvisioningContractError("binding role invalid")
        return self

@dataclass(frozen=True)
class AuthorityEpochBootstrap:
    trust_domain:str; tenant_id:str; organization_id:str; mission_id:str; epoch:int; revoked_grant_ids:tuple[str,...]; administrator_subject_id:str; key_id:str; algorithm:str; issued_at:str; provenance_id:str; signature:str
    def validate(self):
        for n in ("trust_domain","tenant_id","organization_id","mission_id","administrator_subject_id","key_id","algorithm","provenance_id","signature"): _txt(getattr(self,n),n)
        if type(self.epoch) is not int or self.epoch<0 or type(self.revoked_grant_ids) is not tuple or len(set(self.revoked_grant_ids))!=len(self.revoked_grant_ids): raise AuthorityProvisioningContractError("epoch bootstrap invalid")
        for g in self.revoked_grant_ids: _txt(g,"revoked_grant_id")
        _time(self.issued_at,"issued_at"); return self
    def payload(self): self.validate(); d=_unsigned(self); d["revoked_grant_ids"]=list(self.revoked_grant_ids); return b"LION/AUTHORITY-EPOCH-BOOTSTRAP/1\0"+_canon(d)
    def digest(self): return sha256(self.payload()+self.signature.encode()).hexdigest()

@dataclass(frozen=True)
class AuthorityRootBootstrap:
    epoch_bootstrap_digest:str; root_grant_id:str; root_grant_digest:str; administrator_subject_id:str; key_id:str; algorithm:str; issued_at:str; provenance_id:str; signature:str
    def validate(self):
        _hex(self.epoch_bootstrap_digest,"epoch_bootstrap_digest"); _hex(self.root_grant_digest,"root_grant_digest")
        for n in ("root_grant_id","administrator_subject_id","key_id","algorithm","provenance_id","signature"): _txt(getattr(self,n),n)
        _time(self.issued_at,"issued_at"); return self
    def payload(self): self.validate(); return b"LION/AUTHORITY-ROOT-BOOTSTRAP/1\0"+_canon(_unsigned(self))
    def digest(self): return sha256(self.payload()+self.signature.encode()).hexdigest()

@dataclass(frozen=True)
class MergeMethodPolicy:
    policy_id:str; revision:str; repository:str; merge_method:str; administrator_subject_id:str; policy_digest:str; issued_at:str; expires_at:str; key_id:str; algorithm:str; signature:str
    def validate(self):
        for n in ("policy_id","revision","repository","administrator_subject_id","key_id","algorithm","signature"): _txt(getattr(self,n),n)
        if self.merge_method not in MERGE_METHODS: raise AuthorityProvisioningContractError("merge_method invalid")
        if not self.policy_digest.startswith("sha256:") or not _HEX.fullmatch(self.policy_digest[7:]): raise AuthorityProvisioningContractError("policy_digest invalid")
        if _time(self.issued_at,"issued_at")>=_time(self.expires_at,"expires_at"): raise AuthorityProvisioningContractError("policy window invalid")
        return self
    def payload(self): self.validate(); return b"LION/MERGE-METHOD-POLICY/1\0"+_canon(_unsigned(self))

@dataclass(frozen=True)
class PRAuthorityProvisioningTransaction:
    transaction_id:str; request:AuthorityProvisioningRequest; merge_policy:MergeMethodPolicy; epoch_bootstrap:AuthorityEpochBootstrap; root_bootstrap:AuthorityRootBootstrap; issuer_bindings:tuple[AuthorityIssuerBinding,...]; lineage_digest:str; leaf_grant_id:str; provenance_id:str
    def validate(self):
        _txt(self.transaction_id,"transaction_id"); _txt(self.leaf_grant_id,"leaf_grant_id"); _txt(self.provenance_id,"provenance_id"); _hex(self.lineage_digest,"lineage_digest")
        if type(self.request) is not AuthorityProvisioningRequest or type(self.merge_policy) is not MergeMethodPolicy or type(self.epoch_bootstrap) is not AuthorityEpochBootstrap or type(self.root_bootstrap) is not AuthorityRootBootstrap: raise AuthorityProvisioningContractError("transaction type invalid")
        self.request.validate(); self.merge_policy.validate(); self.epoch_bootstrap.validate(); self.root_bootstrap.validate()
        if type(self.issuer_bindings) is not tuple or not self.issuer_bindings: raise AuthorityProvisioningContractError("issuer_bindings invalid")
        for b in self.issuer_bindings:
            if type(b) is not AuthorityIssuerBinding: raise AuthorityProvisioningContractError("issuer binding type invalid")
            b.validate()
        if self.request.repository!=self.merge_policy.repository or self.request.merge_method!=self.merge_policy.merge_method or self.request.policy_digest!=self.merge_policy.policy_digest: raise AuthorityProvisioningContractError("policy/request mismatch")
        if self.root_bootstrap.epoch_bootstrap_digest!=self.epoch_bootstrap.digest() or self.request.mission_id!=self.epoch_bootstrap.mission_id: raise AuthorityProvisioningContractError("authority context mismatch")
        return self
    def digest(self): self.validate(); return _digest(b"LION/PR-AUTHORITY-PROVISIONING-TRANSACTION/1\0",asdict(self))

@dataclass(frozen=True)
class AuthorityProvisioningDecision:
    decision_id:str; transaction_digest:str; decision:str; administrator_subject_id:str; key_id:str; algorithm:str; decided_at:str; signature:str
    def validate(self):
        for n in ("decision_id","administrator_subject_id","key_id","algorithm","signature"): _txt(getattr(self,n),n)
        _hex(self.transaction_digest,"transaction_digest")
        if self.decision not in {"ALLOW","DENY"}: raise AuthorityProvisioningContractError("decision invalid")
        _time(self.decided_at,"decided_at"); return self
    def payload(self): self.validate(); return b"LION/AUTHORITY-PROVISIONING-DECISION/1\0"+_canon(_unsigned(self))

@dataclass(frozen=True)
class AuthorityProvisioningReceipt:
    receipt_id:str; operation_kind:str; transaction_digest:str; request_id:str; repository:str; pr_number:int; base_sha:str; head_sha:str; mission_id:str; merge_method:str; grant_id:str; root_grant_id:str; root_grant_digest:str; epoch:int; administrator_subject_id:str; provenance_id:str; database_identity:str; provisioned_at:str; receipt_digest:str=""
    def validate(self):
        for n in ("receipt_id","operation_kind","transaction_digest","request_id","repository","mission_id","grant_id","root_grant_id","administrator_subject_id","provenance_id","database_identity","provisioned_at"): _txt(getattr(self,n),n,1024)
        _hex(self.transaction_digest,"transaction_digest"); _hex(self.root_grant_digest,"root_grant_digest"); _hex(self.database_identity,"database_identity")
        if self.operation_kind not in {"AUTHORITY_CONTEXT_BOOTSTRAP","PR_AUTHORITY_PROVISIONING"} or type(self.pr_number) is not int or self.pr_number<0 or type(self.epoch) is not int or self.epoch<0: raise AuthorityProvisioningContractError("receipt invalid")
        if self.pr_number:
            _sha(self.base_sha,"base_sha"); _sha(self.head_sha,"head_sha")
            if self.merge_method not in MERGE_METHODS: raise AuthorityProvisioningContractError("receipt merge_method invalid")
        elif self.base_sha or self.head_sha or self.merge_method: raise AuthorityProvisioningContractError("context receipt carries PR fields")
        _time(self.provisioned_at,"provisioned_at")
        if self.receipt_digest and self.receipt_digest!=_digest(b"LION/AUTHORITY-PROVISIONING-RECEIPT/1\0",{k:v for k,v in asdict(self).items() if k!="receipt_digest"}): raise AuthorityProvisioningContractError("receipt digest mismatch")
        return self
    def sealed(self):
        d=asdict(self); d["receipt_digest"]=_digest(b"LION/AUTHORITY-PROVISIONING-RECEIPT/1\0",{k:v for k,v in d.items() if k!="receipt_digest"}); return AuthorityProvisioningReceipt(**d).validate()
