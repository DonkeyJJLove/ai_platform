"""Fail-closed local persistence boundary for externally signed merge authority."""
from __future__ import annotations
from dataclasses import asdict,replace
from datetime import datetime
from hashlib import sha256
import json,sqlite3
from pathlib import Path
from threading import RLock
from typing import Callable
from cyber_lion.contracts.authority_provisioning import AuthorityEpochBootstrap,AuthorityIssuerBinding,AuthorityProvisioningDecision,AuthorityProvisioningReceipt,AuthorityRootBootstrap,MergeMethodPolicy,PRAuthorityProvisioningTransaction
from cyber_lion.enterprise.authority_grant import AuthorityGrant,validate_attenuation
from cyber_lion.enterprise.authority_source import AuthorityLineageRecord,AuthorityLookupKey,canonical_pr_authority_resource,canonical_source_lineage_digest
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext,IssuerKeyBinding,authenticate_authority_grant
from cyber_lion.enterprise.pr_authority_bootstrap import PRAuthorityBootstrapLookupKey,PRAuthorityBootstrapRecord,canonical_pr_bootstrap_digest
Verifier=Callable[[bytes,str,str,str],bool]
_SOURCE="trusted-control-plane"; _DB_DOMAIN=b"LION/AUTHORITY-PROVISIONING-DB/1\0"
class AuthorityProvisioningError(RuntimeError): pass

def authority_provisioning_schema_sql():
 return """CREATE TABLE IF NOT EXISTS authority_epoch_state(trust_domain TEXT NOT NULL,tenant_id TEXT NOT NULL,organization_id TEXT NOT NULL,mission_id TEXT NOT NULL,epoch INTEGER NOT NULL,revoked_json TEXT NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(trust_domain,tenant_id,organization_id,mission_id));
CREATE TABLE IF NOT EXISTS authority_root_anchor(trust_domain TEXT NOT NULL,tenant_id TEXT NOT NULL,organization_id TEXT NOT NULL,mission_id TEXT NOT NULL,epoch INTEGER NOT NULL,root_grant_id TEXT NOT NULL,root_grant_digest TEXT NOT NULL,PRIMARY KEY(trust_domain,tenant_id,organization_id,mission_id,epoch));
CREATE TABLE IF NOT EXISTS pr_bootstrap(repository TEXT NOT NULL,pr_number INTEGER NOT NULL,base_sha TEXT NOT NULL,head_sha TEXT NOT NULL,merge_method TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(repository,pr_number,base_sha,head_sha,merge_method,record_json));
CREATE TABLE IF NOT EXISTS authority_lineage(repository TEXT NOT NULL,pr_number INTEGER NOT NULL,base_sha TEXT NOT NULL,head_sha TEXT NOT NULL,mission_id TEXT NOT NULL,grant_id TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(repository,pr_number,base_sha,head_sha,mission_id,grant_id,record_json));
CREATE TABLE IF NOT EXISTS authority_provisioning_receipt(transaction_digest TEXT NOT NULL PRIMARY KEY,receipt_digest TEXT NOT NULL UNIQUE,operation_kind TEXT NOT NULL,record_json TEXT NOT NULL,provisioned_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS authority_provisioning_receipt_no_update BEFORE UPDATE ON authority_provisioning_receipt BEGIN SELECT RAISE(ABORT,'authority provisioning receipt append-only'); END;
CREATE TRIGGER IF NOT EXISTS authority_provisioning_receipt_no_delete BEFORE DELETE ON authority_provisioning_receipt BEGIN SELECT RAISE(ABORT,'authority provisioning receipt append-only'); END;"""
def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _utc(v):
 try: x=datetime.fromisoformat(v.replace("Z","+00:00"))
 except Exception as e: raise AuthorityProvisioningError("invalid timestamp") from e
 if x.tzinfo is None: raise AuthorityProvisioningError("timestamp must be timezone-aware")
 return x
def _verify(fn,payload,sig,key,alg,label):
 if not callable(fn): raise AuthorityProvisioningError(f"{label} verifier unavailable")
 try: ok=fn(payload,sig,key,alg)
 except Exception as e: raise AuthorityProvisioningError(f"{label} verifier failed closed") from e
 if ok is not True: raise AuthorityProvisioningError(f"{label} signature invalid")
def _binding(bindings,subject,domain,role):
 rows=[b for b in bindings if type(b) is AuthorityIssuerBinding and b.subject_id==subject and b.trust_domain==domain and b.role==role]
 if len(rows)!=1: raise AuthorityProvisioningError(f"{role} binding missing or ambiguous")
 return rows[0].validate()
def _issuer_keys(bindings,domain,lineage):
 out=[]
 for subject in dict.fromkeys(g.issuer_subject_id for g in lineage):
  b=_binding(bindings,subject,domain,"authority-issuer"); out.append(IssuerKeyBinding(b.subject_id,b.trust_domain,b.key_id,b.algorithm).validate())
 return tuple(out)
def _wire_lineage(record):
 d=asdict(record); d["lineage"]=[asdict(g) for g in record.lineage]
 for g in d["lineage"]:
  for k in ("actions","resource_scope","constraints"): g[k]=list(g[k])
 return d
def _wire_bootstrap(record):
 d=asdict(record); d["issuer_key_bindings"]=[asdict(b) for b in record.issuer_key_bindings]; return d

class SQLiteAuthorityProvisioningStore:
 __slots__=("_path","_repo","_lock","_dbid")
 def __init__(self,database_path:str,*,repository_root:str):
  db=Path(database_path); repo=Path(repository_root)
  if not db.is_absolute() or not repo.is_absolute(): raise AuthorityProvisioningError("paths must be absolute")
  try: db=db.resolve(strict=True); repo=repo.resolve(strict=True)
  except OSError as e: raise AuthorityProvisioningError("paths unavailable") from e
  if not db.is_file() or not repo.is_dir() or db==repo or repo in db.parents: raise AuthorityProvisioningError("authority database must exist outside repository tree")
  self._path=str(db); self._repo=str(repo); self._lock=RLock(); self._dbid=sha256(_DB_DOMAIN+self._path.encode()).hexdigest()
 @property
 def database_identity(self): return self._dbid
 def _connect(self): return sqlite3.connect(self._path,timeout=5,isolation_level=None)
 def schema_ready(self):
  needed={"authority_epoch_state","authority_root_anchor","pr_bootstrap","authority_lineage","authority_provisioning_receipt"}; triggers={"authority_provisioning_receipt_no_update","authority_provisioning_receipt_no_delete"}
  try:
   with self._connect() as c:
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}; tr={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
   return needed<=tables and triggers<=tr
  except sqlite3.Error: return False
 def _admin(self,epoch,bindings,verifier,*artifacts):
  b=_binding(bindings,epoch.administrator_subject_id,epoch.trust_domain,"provisioning-administrator")
  if (epoch.key_id,epoch.algorithm)!=(b.key_id,b.algorithm): raise AuthorityProvisioningError("epoch administrator key mismatch")
  _verify(verifier,epoch.payload(),epoch.signature,b.key_id,b.algorithm,"epoch bootstrap")
  for a,label in artifacts:
   if a.administrator_subject_id!=b.subject_id or (a.key_id,a.algorithm)!=(b.key_id,b.algorithm): raise AuthorityProvisioningError(f"{label} administrator mismatch")
   _verify(verifier,a.payload(),a.signature,b.key_id,b.algorithm,label)
  return b
 def bootstrap_authority_context(self,*,epoch_bootstrap,root_bootstrap,root_grant,issuer_bindings,administrator_verifier,authority_verifier,provisioned_at):
  if not self.schema_ready(): raise AuthorityProvisioningError("authority provisioning schema not ready")
  if type(epoch_bootstrap) is not AuthorityEpochBootstrap or type(root_bootstrap) is not AuthorityRootBootstrap or type(root_grant) is not AuthorityGrant or type(issuer_bindings) is not tuple: raise AuthorityProvisioningError("bootstrap types invalid")
  epoch_bootstrap.validate(); root_bootstrap.validate(); root_grant.validate(); when=_utc(provisioned_at)
  if root_bootstrap.epoch_bootstrap_digest!=epoch_bootstrap.digest() or root_bootstrap.root_grant_id!=root_grant.grant_id or root_bootstrap.root_grant_digest!=root_grant.digest(): raise AuthorityProvisioningError("root bootstrap binding mismatch")
  admin=self._admin(epoch_bootstrap,issuer_bindings,administrator_verifier,(root_bootstrap,"root bootstrap"))
  if root_grant.parent_grant_id is not None or root_grant.issuer_subject_id==root_grant.subject_id: raise AuthorityProvisioningError("self-minted or delegated root denied")
  if root_grant.issuer_subject_id==admin.subject_id: raise AuthorityProvisioningError("administrator/issuer separation required")
  if root_grant.epoch!=epoch_bootstrap.epoch or (root_grant.tenant_id,root_grant.organization_id,root_grant.mission_id)!=(epoch_bootstrap.tenant_id,epoch_bootstrap.organization_id,epoch_bootstrap.mission_id): raise AuthorityProvisioningError("root context mismatch")
  if root_grant.grant_id in set(epoch_bootstrap.revoked_grant_ids) or not (_utc(root_grant.issued_at)<=when<_utc(root_grant.expires_at)): raise AuthorityProvisioningError("root not current")
  ctx=AuthorityVerificationContext(epoch_bootstrap.trust_domain,epoch_bootstrap.tenant_id,epoch_bootstrap.organization_id,epoch_bootstrap.mission_id).validate(); authenticate_authority_grant(root_grant,_issuer_keys(issuer_bindings,epoch_bootstrap.trust_domain,(root_grant,)),authority_verifier,context=ctx)
  tx=sha256((epoch_bootstrap.digest()+root_bootstrap.digest()).encode()).hexdigest(); receipt=AuthorityProvisioningReceipt(f"authority-context:{tx}","AUTHORITY_CONTEXT_BOOTSTRAP",tx,f"context:{epoch_bootstrap.mission_id}","authority-control-plane",0,"","",epoch_bootstrap.mission_id,"",root_grant.grant_id,root_grant.grant_id,root_grant.digest(),epoch_bootstrap.epoch,admin.subject_id,root_bootstrap.provenance_id,self._dbid,provisioned_at).sealed(); context=(epoch_bootstrap.trust_domain,epoch_bootstrap.tenant_id,epoch_bootstrap.organization_id,epoch_bootstrap.mission_id); revoked=_canon(sorted(epoch_bootstrap.revoked_grant_ids))
  with self._lock,self._connect() as c:
   try:
    c.execute("BEGIN IMMEDIATE")
    if c.execute("SELECT epoch FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",context).fetchone() is not None: raise AuthorityProvisioningError("authority context replay denied")
    c.execute("INSERT INTO authority_epoch_state(trust_domain,tenant_id,organization_id,mission_id,epoch,revoked_json,version) VALUES(?,?,?,?,?,?,1)",(*context,epoch_bootstrap.epoch,revoked)); c.execute("INSERT INTO authority_root_anchor(trust_domain,tenant_id,organization_id,mission_id,epoch,root_grant_id,root_grant_digest) VALUES(?,?,?,?,?,?,?)",(*context,epoch_bootstrap.epoch,root_grant.grant_id,root_grant.digest())); c.execute("INSERT INTO authority_provisioning_receipt(transaction_digest,receipt_digest,operation_kind,record_json,provisioned_at) VALUES(?,?,?,?,?)",(receipt.transaction_digest,receipt.receipt_digest,receipt.operation_kind,_canon(asdict(receipt)),receipt.provisioned_at)); c.execute("COMMIT")
   except Exception:
    try: c.execute("ROLLBACK")
    except sqlite3.Error: pass
    raise
  return receipt
 def provision_pr_authority(self,*,transaction,decision,lineage,administrator_verifier,authority_verifier,provisioned_at):
  if not self.schema_ready(): raise AuthorityProvisioningError("authority provisioning schema not ready")
  if type(transaction) is not PRAuthorityProvisioningTransaction or type(decision) is not AuthorityProvisioningDecision or type(lineage) is not tuple or not lineage: raise AuthorityProvisioningError("provisioning types invalid")
  transaction.validate(); decision.validate(); when=_utc(provisioned_at)
  for g in lineage:
   if type(g) is not AuthorityGrant: raise AuthorityProvisioningError("lineage type invalid")
   g.validate()
  req=transaction.request; policy=transaction.merge_policy; epoch=transaction.epoch_bootstrap; root=transaction.root_bootstrap; leaf=lineage[-1]; root_grant=lineage[0]
  if decision.decision!="ALLOW" or decision.transaction_digest!=transaction.digest(): raise AuthorityProvisioningError("provisioning decision denied or unbound")
  if not (_utc(policy.issued_at)<=_utc(req.requested_at)<=_utc(decision.decided_at)<=when<_utc(policy.expires_at)): raise AuthorityProvisioningError("provisioning chronology invalid")
  admin=self._admin(epoch,transaction.issuer_bindings,administrator_verifier,(root,"root bootstrap"),(policy,"merge policy"),(decision,"provisioning decision")); issuers={g.issuer_subject_id for g in lineage}
  if req.requester_subject_id in issuers or admin.subject_id in issuers or req.requester_subject_id==admin.subject_id or req.effect_executor_subject_id in issuers or req.effect_executor_subject_id==admin.subject_id: raise AuthorityProvisioningError("authority role separation denied")
  if root.root_grant_id!=root_grant.grant_id or root.root_grant_digest!=root_grant.digest() or root.epoch_bootstrap_digest!=epoch.digest(): raise AuthorityProvisioningError("root evidence mismatch")
  if root_grant.parent_grant_id is not None or root_grant.issuer_subject_id==root_grant.subject_id or leaf.issuer_subject_id==leaf.subject_id: raise AuthorityProvisioningError("self-minted/self-signed authority denied")
  prev=root_grant
  for child in lineage[1:]: validate_attenuation(prev,child); prev=child
  if transaction.lineage_digest!=canonical_source_lineage_digest(lineage) or transaction.leaf_grant_id!=leaf.grant_id: raise AuthorityProvisioningError("lineage binding mismatch")
  keys=_issuer_keys(transaction.issuer_bindings,epoch.trust_domain,lineage); ctx=AuthorityVerificationContext(epoch.trust_domain,epoch.tenant_id,epoch.organization_id,epoch.mission_id).validate()
  for g in lineage:
   authenticate_authority_grant(g,keys,authority_verifier,context=ctx)
   if g.epoch!=epoch.epoch or not (_utc(g.issued_at)<=when<_utc(g.expires_at)): raise AuthorityProvisioningError("lineage not current")
  key=AuthorityLookupKey(req.repository,req.pr_number,req.base_sha,req.head_sha,req.mission_id,leaf.grant_id).validate()
  if leaf.actions!=("merge_pull_request",) or leaf.resource_scope!=(canonical_pr_authority_resource(key),) or leaf.authority_ceiling!="external_write" or f"merge_method:{req.merge_method}" not in leaf.constraints or leaf.policy_digest!=req.policy_digest: raise AuthorityProvisioningError("leaf exact merge binding denied")
  if (leaf.tenant_id,leaf.organization_id,leaf.mission_id)!=(epoch.tenant_id,epoch.organization_id,epoch.mission_id): raise AuthorityProvisioningError("leaf context mismatch")
  ikeys=_issuer_keys(transaction.issuer_bindings,epoch.trust_domain,lineage); bkey=PRAuthorityBootstrapLookupKey(req.repository,req.pr_number,req.base_sha,req.head_sha,req.merge_method).validate(); bootstrap=PRAuthorityBootstrapRecord(bkey,req.mission_id,leaf.grant_id,epoch.trust_domain,epoch.tenant_id,epoch.organization_id,epoch.epoch,root.root_grant_id,root.root_grant_digest,ikeys,transaction.provenance_id,"0"*64,_SOURCE); bootstrap=replace(bootstrap,bootstrap_digest=canonical_pr_bootstrap_digest(bootstrap)).validate(); lrec=AuthorityLineageRecord(key,lineage,canonical_source_lineage_digest(lineage),transaction.provenance_id,_SOURCE).validate(); receipt=AuthorityProvisioningReceipt(f"pr-authority:{transaction.digest()}","PR_AUTHORITY_PROVISIONING",transaction.digest(),req.request_id,req.repository,req.pr_number,req.base_sha,req.head_sha,req.mission_id,req.merge_method,leaf.grant_id,root.root_grant_id,root.root_grant_digest,epoch.epoch,admin.subject_id,transaction.provenance_id,self._dbid,provisioned_at).sealed(); context=(epoch.trust_domain,epoch.tenant_id,epoch.organization_id,epoch.mission_id)
  with self._lock,self._connect() as c:
   try:
    c.execute("BEGIN IMMEDIATE"); er=c.execute("SELECT epoch,revoked_json FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",context).fetchone(); rr=c.execute("SELECT root_grant_id,root_grant_digest FROM authority_root_anchor WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=? AND epoch=?",(*context,epoch.epoch)).fetchone()
    if er is None or int(er[0])!=epoch.epoch or tuple(sorted(json.loads(er[1])))!=tuple(sorted(epoch.revoked_grant_ids)): raise AuthorityProvisioningError("current epoch/revocation mismatch")
    if rr is None or tuple(rr)!=(root.root_grant_id,root.root_grant_digest): raise AuthorityProvisioningError("current root anchor mismatch")
    if any(g.grant_id in set(json.loads(er[1])) for g in lineage): raise AuthorityProvisioningError("revoked authority denied")
    br=c.execute("SELECT record_json FROM pr_bootstrap WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=? AND merge_method=?",(req.repository,req.pr_number,req.base_sha,req.head_sha,req.merge_method)).fetchall(); lr=c.execute("SELECT record_json FROM authority_lineage WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=? AND mission_id=? AND grant_id=?",(req.repository,req.pr_number,req.base_sha,req.head_sha,req.mission_id,leaf.grant_id)).fetchall()
    if bool(br)!=bool(lr): raise AuthorityProvisioningError("partial authority state denied")
    if br or lr or c.execute("SELECT receipt_digest FROM authority_provisioning_receipt WHERE transaction_digest=?",(receipt.transaction_digest,)).fetchone() is not None: raise AuthorityProvisioningError("provisioning replay denied")
    c.execute("INSERT INTO pr_bootstrap(repository,pr_number,base_sha,head_sha,merge_method,record_json) VALUES(?,?,?,?,?,?)",(req.repository,req.pr_number,req.base_sha,req.head_sha,req.merge_method,_canon(_wire_bootstrap(bootstrap)))); c.execute("INSERT INTO authority_lineage(repository,pr_number,base_sha,head_sha,mission_id,grant_id,record_json) VALUES(?,?,?,?,?,?,?)",(req.repository,req.pr_number,req.base_sha,req.head_sha,req.mission_id,leaf.grant_id,_canon(_wire_lineage(lrec)))); c.execute("INSERT INTO authority_provisioning_receipt(transaction_digest,receipt_digest,operation_kind,record_json,provisioned_at) VALUES(?,?,?,?,?)",(receipt.transaction_digest,receipt.receipt_digest,receipt.operation_kind,_canon(asdict(receipt)),receipt.provisioned_at)); c.execute("COMMIT")
   except Exception:
    try: c.execute("ROLLBACK")
    except sqlite3.Error: pass
    raise
  return receipt
