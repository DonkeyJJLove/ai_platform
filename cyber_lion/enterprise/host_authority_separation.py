"""Pure fail-closed evidence and admission brokers for host authority separation.

The module does not perform OS, filesystem, SQLite, GitHub, network, process, authority, merge,
deploy, or migration effects.  It accepts primary evidence bytes/records and deterministically
derives identities that callers previously could self-declare.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from hashlib import sha1, sha256
import json,re
from typing import Any
from cyber_lion.contracts.host_authority_separation import (
    BrokerPermit, CANONICAL_REPOSITORY, CANONICAL_REPOSITORY_PROVIDER, CANONICAL_SNAPSHOTTER_IDENTITY,
    CONTROL_PLANE_GROUP, DEPLOYER_USER, DeploymentReceipt, DeploymentRequest, ExternalAuthorityIdentity,
    HostAuthorityContractError, HostAuthorityObservation, HostAuthoritySeparationPlan, HostOperation,
    HostTransitionPlan, LIVE_DB_PATH, MIGRATOR_USER, MigrationReceipt, PRESERVED_TABLES, PROVISIONING_TABLES,
    PROVISIONING_TRIGGERS, RUNTIME_CODE_PATH, RUNTIME_USER, RUNNER_USER, SERVICE_ENV_PATH, SERVICE_UNIT_PATH,
    SNAPSHOT_DIR, SchemaMigrationRequest, SchemaObservation, SnapshotAttestation, TRUST_CLIENT_GROUP,
    TrustedRuntimeReadBinding,
)
from cyber_lion.enterprise.authority_provisioning import authority_provisioning_schema_sql

class HostAuthoritySeparationError(HostAuthorityContractError): pass

def _canon(v:Any)->bytes: return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _digest(domain:bytes,v:Any)->str: return sha256(domain+_canon(v)).hexdigest()
def _utc(v:str)->None:
    try: d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except Exception as e: raise HostAuthoritySeparationError("timestamp invalid") from e
    if d.tzinfo is None: raise HostAuthoritySeparationError("timestamp must be timezone-aware")
def schema_sql_digest()->str: return sha256(authority_provisioning_schema_sql().encode()).hexdigest()
CANONICAL_SCHEMA_SQL_SHA256="7e9f8873a4b5fb943f183d9546d1a9f08ed9ede19d73e55400dab7f6612a976b"
if schema_sql_digest()!=CANONICAL_SCHEMA_SQL_SHA256: raise RuntimeError("canonical authority provisioning SQL digest drift")

_EVIDENCE_CAP=object()

CANDIDATE_TREE_PROVIDER="git-object-candidate-tree/v1"
SCHEMA_MANIFEST_PROVIDER="sqlite-master-schema-observer/v1"

@dataclass(frozen=True)
class IndependentEvidenceProviderToken:
    provider_id:str; observation_id:str; _cap:object=field(default=None,init=False,repr=False,compare=False)
    def validate(self):
        if self._cap is not _EVIDENCE_CAP: raise HostAuthoritySeparationError("independent evidence provider capability unavailable")
        if not isinstance(self.provider_id,str) or not self.provider_id or not isinstance(self.observation_id,str) or not self.observation_id: raise HostAuthoritySeparationError("independent evidence provider identity invalid")
        return self

def _mint_provider_token(provider_id:str,observation_id:str)->IndependentEvidenceProviderToken:
    # Private capability mint: production callers receive tokens from a separately trusted
    # provider adapter.  Requests/plans cannot select or mint this capability.
    token=IndependentEvidenceProviderToken(provider_id,observation_id); object.__setattr__(token,"_cap",_EVIDENCE_CAP); return token.validate()

def _require_provider(token:IndependentEvidenceProviderToken,expected:str)->None:
    if type(token) is not IndependentEvidenceProviderToken: raise HostAuthoritySeparationError("independent evidence provider token required")
    token.validate()
    if token.provider_id!=expected: raise HostAuthoritySeparationError("independent evidence provider substitution denied")


def _production_path(path:str)->bool:
    return (path.startswith("cyber_lion/") and path.endswith(".py") and "/tests/" not in f"/{path}") or (path.startswith(".github/workflows/") and path.endswith((".yml",".yaml")))

def _path(path:Any)->str:
    if not isinstance(path,str) or not path or path.startswith("/") or "\x00" in path: raise HostAuthoritySeparationError("manifest path invalid")
    parts=path.split("/")
    if any(not p or p in {".",".."} for p in parts): raise HostAuthoritySeparationError("manifest path invalid")
    return path

def _mode(mode:Any)->str:
    if mode not in {"100644","100755","120000"}: raise HostAuthoritySeparationError("manifest mode invalid")
    return mode

def _git_blob_sha(data:bytes)->str:
    if type(data) is not bytes: raise HostAuthoritySeparationError("candidate file bytes required")
    return sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def _git_tree_sha(entries:tuple[tuple[str,str,str],...])->str:
    root:{}={}
    for path,mode,blob_sha in entries:
        _path(path); _mode(mode)
        if not re.fullmatch(r"[0-9a-f]{40}",blob_sha): raise HostAuthoritySeparationError("blob sha invalid")
        node=root; parts=path.split("/")
        for part in parts[:-1]:
            current=node.get(part)
            if current is None: current={}; node[part]=current
            if not isinstance(current,dict): raise HostAuthoritySeparationError("manifest file/directory collision")
            node=current
        if parts[-1] in node: raise HostAuthoritySeparationError("manifest duplicate path")
        node[parts[-1]]=(mode,blob_sha)
    def emit(node:dict)->str:
        rows=[]
        for name,value in node.items():
            if isinstance(value,dict): rows.append((name,True,"40000",emit(value)))
            else: rows.append((name,False,value[0],value[1]))
        rows.sort(key=lambda x:x[0]+("/" if x[1] else ""))
        raw=b"".join(f"{mode} {name}\0".encode()+bytes.fromhex(oid) for name,_,mode,oid in rows)
        return sha1(f"tree {len(raw)}\0".encode()+raw).hexdigest()
    return emit(root)

@dataclass(frozen=True)
class CandidateTreeEvidence:
    tree_sha:str; tracked_file_count:int; production_manifest_sha256:str; production_entry_count:int; provider_observation_id:str
    full_entries:tuple[tuple[str,str,str,str,int],...]; provenance_digest:str; _cap:object=field(default=None,init=False,repr=False,compare=False)
    def validate(self):
        if self._cap is not _EVIDENCE_CAP: raise HostAuthoritySeparationError("candidate tree evidence origin unavailable")
        if not re.fullmatch(r"[0-9a-f]{40}",self.tree_sha): raise HostAuthoritySeparationError("candidate tree evidence sha invalid")
        if type(self.full_entries) is not tuple or not self.full_entries: raise HostAuthoritySeparationError("candidate tree evidence empty")
        git_entries=[]; prod=[]
        for row in self.full_entries:
            if type(row) is not tuple or len(row)!=5: raise HostAuthoritySeparationError("candidate tree entry invalid")
            path,mode,blob_sha,byte_sha,size=row; _path(path); _mode(mode)
            if not re.fullmatch(r"[0-9a-f]{40}",blob_sha) or not re.fullmatch(r"[0-9a-f]{64}",byte_sha) or type(size) is not int or size<0: raise HostAuthoritySeparationError("candidate tree entry identity invalid")
            git_entries.append((path,mode,blob_sha))
            if _production_path(path): prod.append({"path":path,"blob_sha":blob_sha,"byte_sha256":byte_sha,"size":size,"mode":mode})
        if len({r[0] for r in self.full_entries})!=len(self.full_entries): raise HostAuthoritySeparationError("candidate tree duplicate path")
        if _git_tree_sha(tuple(git_entries))!=self.tree_sha: raise HostAuthoritySeparationError("candidate tree reconstruction mismatch")
        manifest=sha256(b"LION/R9D8/EXACT-PRODUCTION-MANIFEST/1\0"+_canon(sorted(prod,key=lambda x:x["path"]))).hexdigest()
        if manifest!=self.production_manifest_sha256 or len(prod)!=self.production_entry_count or len(self.full_entries)!=self.tracked_file_count: raise HostAuthoritySeparationError("candidate production manifest derivation mismatch")
        if not isinstance(self.provider_observation_id,str) or not self.provider_observation_id: raise HostAuthoritySeparationError("candidate tree provider observation invalid")
        expected=_digest(b"LION/CANDIDATE-TREE-EVIDENCE/1\0",{"provider_observation":self.provider_observation_id,"tree_sha":self.tree_sha,"tracked_file_count":self.tracked_file_count,"production_manifest_sha256":manifest,"production_entry_count":len(prod),"full_entries":self.full_entries})
        if expected!=self.provenance_digest: raise HostAuthoritySeparationError("candidate tree evidence digest mismatch")
        return self
    def digest(self): self.validate(); return self.provenance_digest

def derive_candidate_tree_evidence(provider:IndependentEvidenceProviderToken,files:tuple[tuple[str,str,bytes],...])->CandidateTreeEvidence:
    _require_provider(provider,CANDIDATE_TREE_PROVIDER)
    if type(files) is not tuple or not files: raise HostAuthoritySeparationError("candidate file evidence required")
    rows=[]; git_entries=[]; prod=[]
    for item in files:
        if type(item) is not tuple or len(item)!=3: raise HostAuthoritySeparationError("candidate file evidence invalid")
        path,mode,data=item; _path(path); _mode(mode)
        if type(data) is not bytes: raise HostAuthoritySeparationError("candidate file bytes required")
        blob=_git_blob_sha(data); bsha=sha256(data).hexdigest(); row=(path,mode,blob,bsha,len(data)); rows.append(row); git_entries.append((path,mode,blob))
        if _production_path(path): prod.append({"path":path,"blob_sha":blob,"byte_sha256":bsha,"size":len(data),"mode":mode})
    rows=tuple(sorted(rows,key=lambda x:x[0])); tree=_git_tree_sha(tuple(git_entries)); manifest=sha256(b"LION/R9D8/EXACT-PRODUCTION-MANIFEST/1\0"+_canon(sorted(prod,key=lambda x:x["path"]))).hexdigest()
    prov=_digest(b"LION/CANDIDATE-TREE-EVIDENCE/1\0",{"provider_observation":provider.observation_id,"tree_sha":tree,"tracked_file_count":len(rows),"production_manifest_sha256":manifest,"production_entry_count":len(prod),"full_entries":rows})
    e=CandidateTreeEvidence(tree,len(rows),manifest,len(prod),provider.observation_id,rows,prov); object.__setattr__(e,"_cap",_EVIDENCE_CAP); return e.validate()


def _commit_identity(raw:bytes)->tuple[str,str,tuple[str,...]]:
    if type(raw) is not bytes or not raw: raise HostAuthoritySeparationError("git commit object bytes required")
    oid=sha1(f"commit {len(raw)}\0".encode()+raw).hexdigest()
    header=raw.split(b"\n\n",1)[0].splitlines(); trees=[]; parents=[]
    for line in header:
        if line.startswith(b"tree "): trees.append(line[5:].decode())
        elif line.startswith(b"parent "): parents.append(line[7:].decode())
    if len(trees)!=1 or not re.fullmatch(r"[0-9a-f]{40}",trees[0]) or any(not re.fullmatch(r"[0-9a-f]{40}",p) for p in parents): raise HostAuthoritySeparationError("git commit object header invalid")
    return oid,trees[0],tuple(parents)

@dataclass(frozen=True)
class RepositoryCurrentnessEvidence:
    provider_id:str; repository:str; pr_number:int; base_ref:str; base_sha:str; base_tree:str; head_ref:str; head_sha:str; head_tree:str
    synthetic_sha:str; synthetic_tree:str; synthetic_parents:tuple[str,str]; provider_payload_sha256:str; provider_observation_id:str; observed_at:str; provenance_digest:str; _cap:object=field(default=None,init=False,repr=False,compare=False)
    def validate(self):
        if self._cap is not _EVIDENCE_CAP or self.provider_id!=CANONICAL_REPOSITORY_PROVIDER: raise HostAuthoritySeparationError("repository evidence provider substitution denied")
        if self.repository!=CANONICAL_REPOSITORY or type(self.pr_number) is not int or self.pr_number<1: raise HostAuthoritySeparationError("repository evidence identity invalid")
        for ref in (self.base_ref,self.head_ref):
            if not isinstance(ref,str) or not ref or ref.startswith("refs/") or ref.startswith("-"): raise HostAuthoritySeparationError("repository evidence ref invalid")
        for oid in (self.base_sha,self.base_tree,self.head_sha,self.head_tree,self.synthetic_sha,self.synthetic_tree,*self.synthetic_parents):
            if not re.fullmatch(r"[0-9a-f]{40}",oid): raise HostAuthoritySeparationError("repository evidence git oid invalid")
        if self.synthetic_tree!=self.head_tree or self.synthetic_parents!=(self.base_sha,self.head_sha): raise HostAuthoritySeparationError("repository synthetic topology invalid")
        if not re.fullmatch(r"[0-9a-f]{64}",self.provider_payload_sha256): raise HostAuthoritySeparationError("repository provider payload digest invalid")
        _utc(self.observed_at)
        expected=_digest(b"LION/REPOSITORY-CURRENTNESS-EVIDENCE/1\0",{"provider_id":self.provider_id,"repository":self.repository,"pr_number":self.pr_number,"base_ref":self.base_ref,"base_sha":self.base_sha,"base_tree":self.base_tree,"head_ref":self.head_ref,"head_sha":self.head_sha,"head_tree":self.head_tree,"synthetic_sha":self.synthetic_sha,"synthetic_tree":self.synthetic_tree,"synthetic_parents":self.synthetic_parents,"provider_payload_sha256":self.provider_payload_sha256,"provider_observation_id":self.provider_observation_id,"observed_at":self.observed_at})
        if expected!=self.provenance_digest: raise HostAuthoritySeparationError("repository evidence provenance digest mismatch")
        return self
    def digest(self): self.validate(); return self.provenance_digest

def derive_repository_currentness_evidence(provider:IndependentEvidenceProviderToken,*,pr_payload:bytes,base_commit_object:bytes,head_commit_object:bytes,synthetic_commit_object:bytes,observed_at:str)->RepositoryCurrentnessEvidence:
    _require_provider(provider,CANONICAL_REPOSITORY_PROVIDER)
    if type(pr_payload) is not bytes or not pr_payload: raise HostAuthoritySeparationError("repository provider PR payload required")
    try: pr=json.loads(pr_payload.decode("utf-8"))
    except Exception as e: raise HostAuthoritySeparationError("repository provider PR payload invalid") from e
    base_oid,base_tree,_=_commit_identity(base_commit_object); head_oid,head_tree,_=_commit_identity(head_commit_object); syn_oid,syn_tree,syn_parents=_commit_identity(synthetic_commit_object)
    try:
        number=pr["number"]; base=pr["base"]; head=pr["head"]; merge=pr["merge_commit_sha"]
        repository=base["repo"]["full_name"]
        if head["repo"]["full_name"]!=repository: raise KeyError("cross-repository head denied")
        base_ref=base["ref"]; base_sha=base["sha"]; head_ref=head["ref"]; head_sha=head["sha"]
    except Exception as e: raise HostAuthoritySeparationError("repository provider PR shape invalid") from e
    if repository!=CANONICAL_REPOSITORY or base_sha!=base_oid or head_sha!=head_oid or merge!=syn_oid: raise HostAuthoritySeparationError("repository provider object identity mismatch")
    if syn_tree!=head_tree or syn_parents!=(base_oid,head_oid): raise HostAuthoritySeparationError("repository provider synthetic topology mismatch")
    _utc(observed_at)
    pd=sha256(b"LION/GITHUB-PR-GIT-OBJECT-PROVIDER/1\0"+provider.observation_id.encode()+b"\0"+pr_payload+base_commit_object+head_commit_object+synthetic_commit_object).hexdigest()
    data={"provider_id":CANONICAL_REPOSITORY_PROVIDER,"repository":repository,"pr_number":number,"base_ref":base_ref,"base_sha":base_oid,"base_tree":base_tree,"head_ref":head_ref,"head_sha":head_oid,"head_tree":head_tree,"synthetic_sha":syn_oid,"synthetic_tree":syn_tree,"synthetic_parents":syn_parents,"provider_payload_sha256":pd,"provider_observation_id":provider.observation_id,"observed_at":observed_at}
    prov=_digest(b"LION/REPOSITORY-CURRENTNESS-EVIDENCE/1\0",data)
    e=RepositoryCurrentnessEvidence(**data,provenance_digest=prov); object.__setattr__(e,"_cap",_EVIDENCE_CAP); return e.validate()

@dataclass(frozen=True)
class SchemaManifestEvidence:
    entries:tuple[tuple[str,str,str,str],...]; manifest_digest:str; provider_observation_id:str; provenance_digest:str; _cap:object=field(default=None,init=False,repr=False,compare=False)
    def validate(self):
        if self._cap is not _EVIDENCE_CAP or type(self.entries) is not tuple: raise HostAuthoritySeparationError("schema manifest evidence origin unavailable")
        seen=set(); wire=[]
        for row in self.entries:
            if type(row) is not tuple or len(row)!=4: raise HostAuthoritySeparationError("schema manifest row invalid")
            typ,name,tbl,definition=row
            if typ not in {"table","trigger","index","view"} or not all(isinstance(x,str) and x for x in (name,tbl,definition)): raise HostAuthoritySeparationError("schema manifest row invalid")
            if (typ,name) in seen: raise HostAuthoritySeparationError("schema manifest duplicate object")
            seen.add((typ,name)); wire.append({"type":typ,"name":name,"table":tbl,"definition":definition})
        md=sha256(b"LION/SCHEMA-OBJECT-MANIFEST/1\0"+_canon(sorted(wire,key=lambda x:(x["type"],x["name"])))).hexdigest()
        if md!=self.manifest_digest: raise HostAuthoritySeparationError("schema manifest digest mismatch")
        prov=_digest(b"LION/SCHEMA-MANIFEST-EVIDENCE/1\0",{"provider_observation":self.provider_observation_id,"manifest_digest":md,"entries":self.entries})
        if prov!=self.provenance_digest: raise HostAuthoritySeparationError("schema manifest provenance mismatch")
        return self
    def digest(self): self.validate(); return self.manifest_digest

def _normalize_sql(sql:str)->str:
    if not isinstance(sql,str) or not sql.strip(): raise HostAuthoritySeparationError("schema SQL definition invalid")
    return " ".join(sql.strip().split())

def derive_schema_manifest_evidence(provider:IndependentEvidenceProviderToken,rows:tuple[tuple[str,str,str,str],...])->SchemaManifestEvidence:
    _require_provider(provider,SCHEMA_MANIFEST_PROVIDER)
    if type(rows) is not tuple: raise HostAuthoritySeparationError("schema rows must be tuple")
    entries=[]
    for typ,name,tbl,sql in rows:
        if name.startswith("sqlite_"): continue
        entries.append((typ,name,tbl,_normalize_sql(sql)))
    entries=tuple(sorted(entries,key=lambda x:(x[0],x[1])))
    wire=[{"type":a,"name":b,"table":c,"definition":d} for a,b,c,d in entries]
    md=sha256(b"LION/SCHEMA-OBJECT-MANIFEST/1\0"+_canon(wire)).hexdigest(); prov=_digest(b"LION/SCHEMA-MANIFEST-EVIDENCE/1\0",{"provider_observation":provider.observation_id,"manifest_digest":md,"entries":entries})
    e=SchemaManifestEvidence(entries,md,provider.observation_id,prov); object.__setattr__(e,"_cap",_EVIDENCE_CAP); return e.validate()

def _canonical_provisioning_schema_entries()->tuple[tuple[str,str,str,str],...]:
    sql=authority_provisioning_schema_sql(); rows=[]
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\);",sql,re.I|re.S):
        statement=_normalize_sql(m.group(0)[:-1]); rows.append(("table",m.group(1),m.group(1),statement))
    for m in re.finditer(r"CREATE TRIGGER IF NOT EXISTS\s+(\w+)\s+BEFORE\s+(?:UPDATE|DELETE)\s+ON\s+(\w+)\s+BEGIN\s+.*?\s+END;",sql,re.I|re.S):
        statement=_normalize_sql(m.group(0)[:-1]); rows.append(("trigger",m.group(1),m.group(2),statement))
    if len(rows)!=7: raise HostAuthoritySeparationError("canonical schema object extraction mismatch")
    return tuple(rows)

def derive_expected_post_schema_evidence(pre:SchemaManifestEvidence)->SchemaManifestEvidence:
    if type(pre) is not SchemaManifestEvidence: raise HostAuthoritySeparationError("exact pre-schema evidence required")
    pre.validate(); merged={(a,b):(a,b,c,d) for a,b,c,d in pre.entries}
    for row in _canonical_provisioning_schema_entries(): merged.setdefault((row[0],row[1]),row)
    provider=_mint_provider_token(SCHEMA_MANIFEST_PROVIDER,"canonical-post-schema-derivation:"+pre.provenance_digest)
    return derive_schema_manifest_evidence(provider,tuple(merged.values()))

@dataclass(frozen=True)
class SnapshotProvenanceEvidence:
    attestation:SnapshotAttestation; _cap:object=field(default=None,init=False,repr=False,compare=False)
    def validate(self):
        if self._cap is not _EVIDENCE_CAP or type(self.attestation) is not SnapshotAttestation: raise HostAuthoritySeparationError("snapshot provenance origin unavailable")
        self.attestation.validate(); return self
    def digest(self): self.validate(); return self.attestation.provenance_digest

def derive_snapshot_provenance(provider:IndependentEvidenceProviderToken,*,source_observation:SchemaObservation,snapshot_path:str,snapshot_bytes:bytes,integrity_check:str,created_at:str)->SnapshotProvenanceEvidence:
    _require_provider(provider,CANONICAL_SNAPSHOTTER_IDENTITY)
    if type(source_observation) is not SchemaObservation or type(snapshot_bytes) is not bytes or not snapshot_bytes: raise HostAuthoritySeparationError("snapshot primary evidence invalid")
    source_observation.validate(); snap=sha256(snapshot_bytes).hexdigest(); source_obs=source_observation.digest()
    wire={"snapshot_path":snapshot_path,"source_database_sha256":source_observation.database_sha256,"snapshot_sha256":snap,"snapshot_size":len(snapshot_bytes),"snapshotter_identity":CANONICAL_SNAPSHOTTER_IDENTITY,"source_observation_digest":source_obs,"integrity_check":integrity_check,"created_at":created_at,"provider_observation":provider.observation_id}
    prov=_digest(b"LION/SNAPSHOT-BYTE-PROVENANCE/1\0",wire)
    attwire={k:v for k,v in wire.items() if k!="provider_observation"}
    att=SnapshotAttestation(**attwire,provenance_digest=prov).validate()
    e=SnapshotProvenanceEvidence(att); object.__setattr__(e,"_cap",_EVIDENCE_CAP); return e.validate()


def _validate_add_only_schema_sql(sql:str)->None:
    low=sql.lower()
    if low.count("create table if not exists ")!=5 or low.count("create trigger if not exists ")!=2: raise HostAuthoritySeparationError("canonical add-only object count mismatch")
    if re.search(r"\bdrop\b|\balter\b|\binsert\s+into\b|\bupdate\s+\w+\s+set\b|\bdelete\s+from\b|\breplace\s+into\b|\bvacuum\b|\battach\b|\bdetach\b",low): raise HostAuthoritySeparationError("destructive or data-mutating schema SQL denied")
    for trigger in PROVISIONING_TRIGGERS:
        if trigger not in low: raise HostAuthoritySeparationError("append-only trigger missing")
    if low.count("select raise(abort")!=2: raise HostAuthoritySeparationError("append-only trigger guards missing")
    required=set(PROVISIONING_TABLES+PRESERVED_TABLES+PROVISIONING_TRIGGERS)
    if any(name not in low for name in required): raise HostAuthoritySeparationError("schema SQL missing canonical objects")

class HostAuthoritySeparationBroker:
    @staticmethod
    def canonical_plan(*,repository_evidence:RepositoryCurrentnessEvidence,candidate_tree_evidence:CandidateTreeEvidence,pre_schema_evidence:SchemaManifestEvidence,trusted_runtime_reads:tuple[TrustedRuntimeReadBinding,...],generated_at:str)->HostAuthoritySeparationPlan:
        if type(repository_evidence) is not RepositoryCurrentnessEvidence or type(candidate_tree_evidence) is not CandidateTreeEvidence or type(pre_schema_evidence) is not SchemaManifestEvidence: raise HostAuthoritySeparationError("canonical provenance evidence required")
        repository_evidence.validate(); candidate_tree_evidence.validate(); pre_schema_evidence.validate()
        if repository_evidence.head_tree!=candidate_tree_evidence.tree_sha: raise HostAuthoritySeparationError("candidate tree evidence not bound to repository head")
        post=derive_expected_post_schema_evidence(pre_schema_evidence)
        plan=HostAuthoritySeparationPlan(
            plan_id=f"host-separation:{repository_evidence.head_sha}",repository=repository_evidence.repository,pr_number=repository_evidence.pr_number,
            baseline_ref=repository_evidence.base_ref,baseline_sha=repository_evidence.base_sha,baseline_tree=repository_evidence.base_tree,
            certified_candidate_ref=repository_evidence.head_ref,certified_candidate_sha=repository_evidence.head_sha,certified_candidate_tree=repository_evidence.head_tree,
            certified_synthetic_sha=repository_evidence.synthetic_sha,certified_repository_evidence_digest=repository_evidence.digest(),
            certified_source_manifest_sha256=candidate_tree_evidence.production_manifest_sha256,certified_pre_schema_manifest_digest=pre_schema_evidence.digest(),certified_post_schema_digest=post.digest(),
            runtime_user=RUNTIME_USER,runner_user=RUNNER_USER,deployer_user=DEPLOYER_USER,migrator_user=MIGRATOR_USER,control_plane_group=CONTROL_PLANE_GROUP,trust_client_group=TRUST_CLIENT_GROUP,
            runtime_code_path=RUNTIME_CODE_PATH,live_db_path=LIVE_DB_PATH,service_env_path=SERVICE_ENV_PATH,service_unit_path=SERVICE_UNIT_PATH,
            runtime_code_owner="root",runtime_code_group=CONTROL_PLANE_GROUP,runtime_code_dir_mode=0o550,runtime_code_file_mode=0o440,
            runner_target_groups=(RUNNER_USER,TRUST_CLIENT_GROUP),trusted_runtime_reads=trusted_runtime_reads,production_private_key_on_host=False,generated_at=generated_at)
        return plan.validate()

    @staticmethod
    def derive_transition(observation:HostAuthorityObservation,plan:HostAuthoritySeparationPlan,*,generated_at:str)->HostTransitionPlan:
        if type(observation) is not HostAuthorityObservation or type(plan) is not HostAuthoritySeparationPlan: raise HostAuthoritySeparationError("exact observation and plan required")
        observation.validate(); plan.validate()
        if (observation.runtime_user,observation.runner_user)!=(plan.runtime_user,plan.runner_user): raise HostAuthoritySeparationError("host principal currentness drift")
        ops=[]
        if CONTROL_PLANE_GROUP in observation.runner_groups: ops.append(HostOperation("REMOVE_RUNNER_CONTROL_PLANE_GROUP",RUNNER_USER,CONTROL_PLANE_GROUP,None,"remove runner from control-plane supplementary group"))
        if TRUST_CLIENT_GROUP not in observation.runner_groups:
            ops.append(HostOperation("ENSURE_TRUST_CLIENT_GROUP",DEPLOYER_USER,TRUST_CLIENT_GROUP,None,"ensure dedicated non-authority trust-client group")); ops.append(HostOperation("ADD_RUNNER_TRUST_CLIENT_GROUP",RUNNER_USER,TRUST_CLIENT_GROUP,None,"grant only bounded external-runtime read membership"))
        ops.extend((HostOperation("REOWN_RUNTIME_CODE_ROOT",DEPLOYER_USER,RUNTIME_CODE_PATH,observation.deployed_manifest_sha256,"root owns immutable runtime code"),HostOperation("SET_RUNTIME_CODE_READ_ONLY",DEPLOYER_USER,RUNTIME_CODE_PATH,observation.deployed_manifest_sha256,"directories 0550 files 0440; runtime is read-only")))
        for b in plan.trusted_runtime_reads: ops.append(HostOperation("PIN_TRUST_CLIENT_RUNTIME_READ",DEPLOYER_USER,b.path,b.sha256_digest,"expose this file read-only to trust-client group only"))
        ops.extend((HostOperation("DENY_RUNNER_DB_ACCESS",DEPLOYER_USER,LIVE_DB_PATH,observation.live_db_sha256,"runner must have neither read nor write access"),HostOperation("DENY_RUNNER_SERVICE_ENV_ACCESS",DEPLOYER_USER,SERVICE_ENV_PATH,None,"runner must not read service credential environment"),HostOperation("INSTALL_BOUNDED_DEPLOYMENT_BROKER",DEPLOYER_USER,RUNTIME_CODE_PATH,None,"fixed operation, fixed destination, no arbitrary shell"),HostOperation("INSTALL_BOUNDED_SCHEMA_MIGRATION_BROKER",MIGRATOR_USER,LIVE_DB_PATH,None,"exact add-only schema transition only")))
        uniq=[]; seen=set()
        for op in ops:
            op.validate(); key=(op.kind,op.target)
            if key not in seen: seen.add(key); uniq.append(op)
        return HostTransitionPlan(f"host-transition:{observation.digest()[:20]}:{plan.digest()[:20]}",observation.digest(),plan.digest(),tuple(uniq),generated_at).validate()

    @staticmethod
    def target_observation_is_separated(observation:HostAuthorityObservation)->bool:
        observation.validate(); return (CONTROL_PLANE_GROUP not in observation.runner_groups and TRUST_CLIENT_GROUP in observation.runner_groups and not observation.runner_db_read and not observation.runner_db_write and not observation.runner_service_env_read and not observation.runtime_code_write and not observation.runner_actions_private_key_read and not observation.runner_authority_private_key_read)


def _assert_repo_plan(repo:RepositoryCurrentnessEvidence,plan:HostAuthoritySeparationPlan)->None:
    repo.validate(); plan.validate()
    exact=(repo.repository,repo.pr_number,repo.base_ref,repo.base_sha,repo.base_tree,repo.head_ref,repo.head_sha,repo.head_tree,repo.synthetic_sha,repo.digest())
    wanted=(plan.repository,plan.pr_number,plan.baseline_ref,plan.baseline_sha,plan.baseline_tree,plan.certified_candidate_ref,plan.certified_candidate_sha,plan.certified_candidate_tree,plan.certified_synthetic_sha,plan.certified_repository_evidence_digest)
    if exact!=wanted: raise HostAuthoritySeparationError("repository currentness evidence not bound to certified plan")

def _deployment_currentness_digest(request:DeploymentRequest,repo:RepositoryCurrentnessEvidence,tree:CandidateTreeEvidence,current_deployed_manifest_sha256:str,current_service_unit_sha256:str)->str:
    return _digest(b"LION/DEPLOYMENT-CURRENTNESS/2\0",{"request":request.digest(),"repository_evidence":repo.digest(),"candidate_tree_evidence":tree.digest(),"deployed_manifest_sha256":current_deployed_manifest_sha256,"service_unit_sha256":current_service_unit_sha256})

def _migration_currentness_digest(request:SchemaMigrationRequest,repo:RepositoryCurrentnessEvidence,before:SchemaObservation,pre:SchemaManifestEvidence,snapshot:SnapshotProvenanceEvidence,post:SchemaManifestEvidence)->str:
    return _digest(b"LION/MIGRATION-CURRENTNESS/2\0",{"request":request.digest(),"repository_evidence":repo.digest(),"before":before.digest(),"pre_schema_evidence":pre.provenance_digest,"snapshot_provenance":snapshot.digest(),"expected_post_schema":post.digest()})

class BoundedDeploymentBroker:
    @staticmethod
    def admit(request:DeploymentRequest,*,plan:HostAuthoritySeparationPlan,authority:ExternalAuthorityIdentity,repository_evidence:RepositoryCurrentnessEvidence,candidate_tree_evidence:CandidateTreeEvidence,current_deployed_manifest_sha256:str,current_service_unit_sha256:str,issued_at:str)->BrokerPermit:
        if type(request) is not DeploymentRequest or type(plan) is not HostAuthoritySeparationPlan or type(authority) is not ExternalAuthorityIdentity or type(repository_evidence) is not RepositoryCurrentnessEvidence or type(candidate_tree_evidence) is not CandidateTreeEvidence: raise HostAuthoritySeparationError("exact deployment admission evidence required")
        request.validate(); plan.validate(); authority.validate(); repository_evidence.validate(); candidate_tree_evidence.validate(); _assert_repo_plan(repository_evidence,plan)
        if authority.host_principal in {plan.deployer_user,plan.migrator_user,plan.runtime_user,plan.runner_user}: raise HostAuthoritySeparationError("authority issuer overlaps host execution principal")
        if request.separation_plan_digest!=plan.digest(): raise HostAuthoritySeparationError("deployment plan digest mismatch")
        reqrepo=(request.repository,request.pr_number,request.baseline_ref,request.baseline_sha,request.baseline_tree,request.candidate_ref,request.candidate_sha,request.candidate_tree,request.synthetic_sha,request.repository_evidence_digest)
        evidence=(repository_evidence.repository,repository_evidence.pr_number,repository_evidence.base_ref,repository_evidence.base_sha,repository_evidence.base_tree,repository_evidence.head_ref,repository_evidence.head_sha,repository_evidence.head_tree,repository_evidence.synthetic_sha,repository_evidence.digest())
        if reqrepo!=evidence: raise HostAuthoritySeparationError("deployment request repository provenance mismatch")
        if candidate_tree_evidence.tree_sha!=repository_evidence.head_tree or request.source_manifest_sha256!=candidate_tree_evidence.production_manifest_sha256 or request.source_manifest_sha256!=plan.certified_source_manifest_sha256: raise HostAuthoritySeparationError("deployment source manifest provenance mismatch")
        for value,name in ((current_deployed_manifest_sha256,"deployed manifest"),(current_service_unit_sha256,"service unit")):
            if not re.fullmatch(r"[0-9a-f]{64}",value): raise HostAuthoritySeparationError(f"{name} digest invalid")
        if (request.current_deployed_manifest_sha256,request.service_unit_sha256)!=(current_deployed_manifest_sha256,current_service_unit_sha256): raise HostAuthoritySeparationError("deployed host currentness drift")
        aid=_digest(b"LION/EXTERNAL-AUTHORITY-IDENTITY/1\0",asdict(authority)); currentness=_deployment_currentness_digest(request,repository_evidence,candidate_tree_evidence,current_deployed_manifest_sha256,current_service_unit_sha256)
        return BrokerPermit(f"deployment-permit:{request.digest()}","DEPLOY_EXACT_CANDIDATE",request.digest(),plan.digest(),DEPLOYER_USER,RUNTIME_CODE_PATH,candidate_tree_evidence.production_manifest_sha256,currentness,current_deployed_manifest_sha256,aid,issued_at).validate()

    @staticmethod
    def revalidate_before_effect(request:DeploymentRequest,permit:BrokerPermit,*,plan:HostAuthoritySeparationPlan,repository_evidence:RepositoryCurrentnessEvidence,candidate_tree_evidence:CandidateTreeEvidence,current_deployed_manifest_sha256:str,current_service_unit_sha256:str)->BrokerPermit:
        request.validate(); permit.validate(); plan.validate(); repository_evidence.validate(); candidate_tree_evidence.validate(); _assert_repo_plan(repository_evidence,plan)
        if permit.operation_kind!="DEPLOY_EXACT_CANDIDATE" or permit.fixed_executor_principal!=DEPLOYER_USER or permit.fixed_destination!=RUNTIME_CODE_PATH: raise HostAuthoritySeparationError("deployment permit identity mismatch")
        if permit.request_digest!=request.digest() or permit.separation_plan_digest!=plan.digest(): raise HostAuthoritySeparationError("deployment permit binding mismatch")
        if request.repository_evidence_digest!=repository_evidence.digest() or request.source_manifest_sha256!=candidate_tree_evidence.production_manifest_sha256 or candidate_tree_evidence.tree_sha!=repository_evidence.head_tree: raise HostAuthoritySeparationError("deployment provenance drift")
        if permit.fixed_payload_digest!=candidate_tree_evidence.production_manifest_sha256: raise HostAuthoritySeparationError("deployment payload digest mismatch")
        if (request.current_deployed_manifest_sha256,request.service_unit_sha256)!=(current_deployed_manifest_sha256,current_service_unit_sha256): raise HostAuthoritySeparationError("deployed host currentness drift")
        expected=_deployment_currentness_digest(request,repository_evidence,candidate_tree_evidence,current_deployed_manifest_sha256,current_service_unit_sha256)
        if permit.currentness_digest!=expected or permit.recovery_evidence_digest!=current_deployed_manifest_sha256: raise HostAuthoritySeparationError("deployment permit stale currentness evidence")
        return permit

    @staticmethod
    def verify_receipt(request:DeploymentRequest,permit:BrokerPermit,receipt:DeploymentReceipt)->DeploymentReceipt:
        request.validate(); permit.validate(); receipt.validate()
        if permit.operation_kind!="DEPLOY_EXACT_CANDIDATE" or permit.request_digest!=request.digest(): raise HostAuthoritySeparationError("deployment permit/request mismatch")
        if receipt.request_digest!=request.digest() or receipt.permit_digest!=permit.digest(): raise HostAuthoritySeparationError("deployment receipt binding mismatch")
        if receipt.pre_manifest_sha256!=request.current_deployed_manifest_sha256: raise HostAuthoritySeparationError("deployment receipt pre-state mismatch")
        if (receipt.deployed_candidate_sha,receipt.deployed_candidate_tree)!=(request.candidate_sha,request.candidate_tree): raise HostAuthoritySeparationError("deployment receipt candidate mismatch")
        if receipt.status=="ROLLED_BACK" and receipt.post_manifest_sha256!=receipt.pre_manifest_sha256: raise HostAuthoritySeparationError("deployment rollback receipt mismatch")
        return receipt

class BoundedSchemaMigrationBroker:
    @staticmethod
    def admit(request:SchemaMigrationRequest,*,plan:HostAuthoritySeparationPlan,authority:ExternalAuthorityIdentity,repository_evidence:RepositoryCurrentnessEvidence,before:SchemaObservation,pre_schema_evidence:SchemaManifestEvidence,snapshot_evidence:SnapshotProvenanceEvidence,issued_at:str)->BrokerPermit:
        if type(request) is not SchemaMigrationRequest or type(plan) is not HostAuthoritySeparationPlan or type(authority) is not ExternalAuthorityIdentity or type(repository_evidence) is not RepositoryCurrentnessEvidence or type(before) is not SchemaObservation or type(pre_schema_evidence) is not SchemaManifestEvidence or type(snapshot_evidence) is not SnapshotProvenanceEvidence: raise HostAuthoritySeparationError("exact migration admission evidence required")
        request.validate(); plan.validate(); authority.validate(); repository_evidence.validate(); before.validate(); pre_schema_evidence.validate(); snapshot_evidence.validate(); _assert_repo_plan(repository_evidence,plan)
        if authority.host_principal in {plan.deployer_user,plan.migrator_user,plan.runtime_user,plan.runner_user}: raise HostAuthoritySeparationError("authority issuer overlaps migration principal")
        _validate_add_only_schema_sql(authority_provisioning_schema_sql())
        if request.schema_sql_sha256!=CANONICAL_SCHEMA_SQL_SHA256: raise HostAuthoritySeparationError("schema digest substitution denied")
        if request.separation_plan_digest!=plan.digest(): raise HostAuthoritySeparationError("migration plan digest mismatch")
        reqrepo=(request.repository,request.pr_number,request.candidate_ref,request.candidate_sha,request.candidate_tree,request.synthetic_sha,request.repository_evidence_digest)
        evidence=(repository_evidence.repository,repository_evidence.pr_number,repository_evidence.head_ref,repository_evidence.head_sha,repository_evidence.head_tree,repository_evidence.synthetic_sha,repository_evidence.digest())
        if reqrepo!=evidence: raise HostAuthoritySeparationError("migration request repository provenance mismatch")
        if request.live_database_sha256!=before.database_sha256 or request.pre_schema_digest!=before.schema_digest or before.schema_digest!=pre_schema_evidence.digest() or plan.certified_pre_schema_manifest_digest!=pre_schema_evidence.digest(): raise HostAuthoritySeparationError("pre-schema provenance mismatch")
        snapshot=snapshot_evidence.attestation
        if snapshot.source_database_sha256!=before.database_sha256 or snapshot.source_observation_digest!=before.digest() or request.snapshot_sha256!=snapshot.snapshot_sha256: raise HostAuthoritySeparationError("snapshot provenance mismatch")
        post=derive_expected_post_schema_evidence(pre_schema_evidence)
        if request.expected_post_schema_digest!=post.digest() or plan.certified_post_schema_digest!=post.digest(): raise HostAuthoritySeparationError("post-schema provenance mismatch")
        aid=_digest(b"LION/EXTERNAL-AUTHORITY-IDENTITY/1\0",asdict(authority)); currentness=_migration_currentness_digest(request,repository_evidence,before,pre_schema_evidence,snapshot_evidence,post)
        return BrokerPermit(f"migration-permit:{request.digest()}","MIGRATE_EXACT_SCHEMA",request.digest(),plan.digest(),MIGRATOR_USER,LIVE_DB_PATH,CANONICAL_SCHEMA_SQL_SHA256,currentness,snapshot_evidence.digest(),aid,issued_at).validate()

    @staticmethod
    def revalidate_before_effect(request:SchemaMigrationRequest,permit:BrokerPermit,*,plan:HostAuthoritySeparationPlan,repository_evidence:RepositoryCurrentnessEvidence,before:SchemaObservation,pre_schema_evidence:SchemaManifestEvidence,snapshot_evidence:SnapshotProvenanceEvidence)->BrokerPermit:
        request.validate(); permit.validate(); plan.validate(); repository_evidence.validate(); before.validate(); pre_schema_evidence.validate(); snapshot_evidence.validate(); _assert_repo_plan(repository_evidence,plan)
        if permit.operation_kind!="MIGRATE_EXACT_SCHEMA" or permit.fixed_executor_principal!=MIGRATOR_USER or permit.fixed_destination!=LIVE_DB_PATH: raise HostAuthoritySeparationError("migration permit identity mismatch")
        if permit.request_digest!=request.digest() or permit.separation_plan_digest!=plan.digest() or permit.fixed_payload_digest!=CANONICAL_SCHEMA_SQL_SHA256: raise HostAuthoritySeparationError("migration permit binding mismatch")
        if request.repository_evidence_digest!=repository_evidence.digest() or request.pre_schema_digest!=pre_schema_evidence.digest() or before.schema_digest!=pre_schema_evidence.digest(): raise HostAuthoritySeparationError("migration provenance drift")
        snapshot=snapshot_evidence.attestation
        if request.live_database_sha256!=before.database_sha256 or request.snapshot_sha256!=snapshot.snapshot_sha256 or snapshot.source_observation_digest!=before.digest(): raise HostAuthoritySeparationError("snapshot currentness drift")
        post=derive_expected_post_schema_evidence(pre_schema_evidence)
        if request.expected_post_schema_digest!=post.digest() or plan.certified_post_schema_digest!=post.digest(): raise HostAuthoritySeparationError("post-schema provenance drift")
        expected=_migration_currentness_digest(request,repository_evidence,before,pre_schema_evidence,snapshot_evidence,post)
        if permit.currentness_digest!=expected or permit.recovery_evidence_digest!=snapshot_evidence.digest(): raise HostAuthoritySeparationError("migration permit stale currentness evidence")
        return permit

    @staticmethod
    def verify_postcondition(before:SchemaObservation,after:SchemaObservation,*,pre_schema_evidence:SchemaManifestEvidence,after_schema_evidence:SchemaManifestEvidence)->SchemaObservation:
        before.validate(); after.validate(); pre_schema_evidence.validate(); after_schema_evidence.validate()
        if before.schema_digest!=pre_schema_evidence.digest() or after.schema_digest!=after_schema_evidence.digest(): raise HostAuthoritySeparationError("schema observation provenance mismatch")
        expected=derive_expected_post_schema_evidence(pre_schema_evidence)
        if after_schema_evidence.digest()!=expected.digest(): raise HostAuthoritySeparationError("post-schema manifest mismatch")
        if before.pr_bootstrap_rows!=after.pr_bootstrap_rows or before.authority_lineage_rows!=after.authority_lineage_rows: raise HostAuthoritySeparationError("historical authority rows changed during migration")
        required=set(PROVISIONING_TABLES+PRESERVED_TABLES+PROVISIONING_TRIGGERS)
        if not required.issubset(set(after.objects)): raise HostAuthoritySeparationError("partial migration denied")
        if after.database_sha256==before.database_sha256: raise HostAuthoritySeparationError("migration produced no database state change")
        return after

    @staticmethod
    def verify_receipt(request:SchemaMigrationRequest,permit:BrokerPermit,before:SchemaObservation,pre_schema_evidence:SchemaManifestEvidence,snapshot_evidence:SnapshotProvenanceEvidence,after:SchemaObservation,after_schema_evidence:SchemaManifestEvidence,receipt:MigrationReceipt)->MigrationReceipt:
        request.validate(); permit.validate(); before.validate(); pre_schema_evidence.validate(); snapshot_evidence.validate(); after.validate(); after_schema_evidence.validate(); receipt.validate()
        snapshot=snapshot_evidence.attestation
        if permit.operation_kind!="MIGRATE_EXACT_SCHEMA" or permit.request_digest!=request.digest(): raise HostAuthoritySeparationError("migration permit/request mismatch")
        if receipt.request_digest!=request.digest() or receipt.permit_digest!=permit.digest(): raise HostAuthoritySeparationError("migration receipt binding mismatch")
        if receipt.snapshot_sha256!=request.snapshot_sha256 or receipt.snapshot_sha256!=snapshot.snapshot_sha256: raise HostAuthoritySeparationError("migration receipt snapshot mismatch")
        if receipt.pre_schema_digest!=request.pre_schema_digest or receipt.pre_schema_digest!=before.schema_digest or receipt.pre_schema_digest!=pre_schema_evidence.digest(): raise HostAuthoritySeparationError("migration receipt pre-schema mismatch")
        if (receipt.preserved_pr_bootstrap_rows,receipt.preserved_authority_lineage_rows)!=(before.pr_bootstrap_rows,before.authority_lineage_rows): raise HostAuthoritySeparationError("migration receipt historical row mismatch")
        if receipt.status=="MIGRATED":
            BoundedSchemaMigrationBroker.verify_postcondition(before,after,pre_schema_evidence=pre_schema_evidence,after_schema_evidence=after_schema_evidence)
            if receipt.post_schema_digest!=after.schema_digest: raise HostAuthoritySeparationError("migration receipt post-schema mismatch")
        else:
            if after.database_sha256!=before.database_sha256 or after.schema_digest!=before.schema_digest or receipt.post_schema_digest!=before.schema_digest: raise HostAuthoritySeparationError("migration rollback receipt mismatch")
        return receipt