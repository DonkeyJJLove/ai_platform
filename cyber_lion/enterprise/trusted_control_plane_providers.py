"""Concrete persistent providers for the trusted control-plane service."""
from __future__ import annotations
from collections.abc import Callable, Mapping
import json, sqlite3
from pathlib import Path
from threading import RLock
from .trusted_control_plane_service import TrustedControlPlaneStore, TrustedSignatureVerifier

class TrustedControlPlaneProviderError(RuntimeError): pass

def _canonical_json(v):
    if not isinstance(v,Mapping): raise TrustedControlPlaneProviderError("provider record must be a mapping")
    return json.dumps(dict(v),sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _decode_record(raw):
    try:v=json.loads(raw)
    except (TypeError,json.JSONDecodeError) as exc: raise TrustedControlPlaneProviderError("persistent provider record is corrupt") from exc
    if not isinstance(v,Mapping): raise TrustedControlPlaneProviderError("persistent provider record is not an object")
    return dict(v)

class SQLiteTrustedControlPlaneStore(TrustedControlPlaneStore):
    BUILDER_LOOKUP_FIELDS=("repository","builder_subject_id","builder_instance_id","candidate_scope_digest","resource_scope_digest","capability_class")
    RUNTIME_PROVIDER_LOOKUP_FIELDS=("provider_id","process_profile_digest","launch_policy_digest","capability_class")
    def __init__(self,database_path):
        if not isinstance(database_path,str) or not database_path.strip(): raise TrustedControlPlaneProviderError("database_path is required")
        self._path=str(Path(database_path));self._lock=RLock();self._initialize()
    def _connect(self):
        c=sqlite3.connect(self._path,timeout=5,isolation_level=None);c.execute("PRAGMA foreign_keys=ON");c.execute("PRAGMA journal_mode=WAL");return c
    def _initialize(self):
        with self._lock,self._connect() as c:c.executescript("""
        CREATE TABLE IF NOT EXISTS pr_bootstrap(repository TEXT NOT NULL,pr_number INTEGER NOT NULL,base_sha TEXT NOT NULL,head_sha TEXT NOT NULL,merge_method TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(repository,pr_number,base_sha,head_sha,merge_method,record_json));
        CREATE TABLE IF NOT EXISTS authority_lineage(repository TEXT NOT NULL,pr_number INTEGER NOT NULL,base_sha TEXT NOT NULL,head_sha TEXT NOT NULL,mission_id TEXT NOT NULL,grant_id TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(repository,pr_number,base_sha,head_sha,mission_id,grant_id,record_json));
        CREATE TABLE IF NOT EXISTS builder_subject(repository TEXT NOT NULL,builder_subject_id TEXT NOT NULL,builder_instance_id TEXT NOT NULL,candidate_scope_digest TEXT NOT NULL,resource_scope_digest TEXT NOT NULL,capability_class TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(repository,builder_subject_id,builder_instance_id,candidate_scope_digest,resource_scope_digest,capability_class,record_json));
        CREATE TABLE IF NOT EXISTS builder_process_runtime_provider(provider_id TEXT NOT NULL,process_profile_digest TEXT NOT NULL,launch_policy_digest TEXT NOT NULL,capability_class TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(provider_id,process_profile_digest,launch_policy_digest,capability_class,record_json));
        """)
    @staticmethod
    def _lookup(record,fields,label):
        lookup=record.get("lookup_key") if isinstance(record,Mapping) else None
        if not isinstance(lookup,Mapping) or frozenset(lookup.keys())!=frozenset(fields): raise TrustedControlPlaneProviderError(f"{label} lookup_key invalid")
        return lookup
    def put_pr_bootstrap(self,record):
        f=("repository","pr_number","base_sha","head_sha","merge_method");l=self._lookup(record,f,"bootstrap");raw=_canonical_json(record)
        with self._lock,self._connect() as c:c.execute("BEGIN IMMEDIATE");c.execute("INSERT OR IGNORE INTO pr_bootstrap VALUES(?,?,?,?,?,?)",tuple(l[n] for n in f)+(raw,));c.execute("COMMIT")
    def put_authority_record(self,record):
        f=("repository","pr_number","base_sha","head_sha","mission_id","grant_id");l=self._lookup(record,f,"authority");raw=_canonical_json(record)
        with self._lock,self._connect() as c:c.execute("BEGIN IMMEDIATE");c.execute("INSERT OR IGNORE INTO authority_lineage VALUES(?,?,?,?,?,?,?)",tuple(l[n] for n in f)+(raw,));c.execute("COMMIT")
    def put_builder_subject_record(self,record):
        f=self.BUILDER_LOOKUP_FIELDS;l=self._lookup(record,f,"builder subject")
        if record.get("record_kind")!="builder-subject" or not isinstance(record.get("subject"),Mapping): raise TrustedControlPlaneProviderError("builder subject record invalid")
        raw=_canonical_json(record)
        with self._lock,self._connect() as c:c.execute("BEGIN IMMEDIATE");c.execute("INSERT OR IGNORE INTO builder_subject VALUES(?,?,?,?,?,?,?)",tuple(l[n] for n in f)+(raw,));c.execute("COMMIT")
    def put_builder_process_runtime_provider_record(self,record):
        f=self.RUNTIME_PROVIDER_LOOKUP_FIELDS;l=self._lookup(record,f,"builder process runtime provider")
        if record.get("record_kind")!="builder-process-runtime-provider" or not isinstance(record.get("provider"),Mapping): raise TrustedControlPlaneProviderError("runtime provider record invalid")
        raw=_canonical_json(record)
        with self._lock,self._connect() as c:c.execute("BEGIN IMMEDIATE");c.execute("INSERT OR IGNORE INTO builder_process_runtime_provider VALUES(?,?,?,?,?)",tuple(l[n] for n in f)+(raw,));c.execute("COMMIT")
    def lookup_pr_bootstrap_exact(self,*,repository,pr_number,base_sha,head_sha,merge_method):
        with self._lock,self._connect() as c:rows=c.execute("SELECT record_json FROM pr_bootstrap WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=? AND merge_method=? ORDER BY record_json",(repository,pr_number,base_sha,head_sha,merge_method)).fetchall()
        return tuple(_decode_record(x[0]) for x in rows)
    def lookup_authority_exact(self,*,repository,pr_number,base_sha,head_sha,mission_id,grant_id):
        with self._lock,self._connect() as c:rows=c.execute("SELECT record_json FROM authority_lineage WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=? AND mission_id=? AND grant_id=? ORDER BY record_json",(repository,pr_number,base_sha,head_sha,mission_id,grant_id)).fetchall()
        return tuple(_decode_record(x[0]) for x in rows)
    def lookup_builder_subject_exact(self,*,repository,builder_subject_id,builder_instance_id,candidate_scope_digest,resource_scope_digest,capability_class):
        with self._lock,self._connect() as c:rows=c.execute("SELECT record_json FROM builder_subject WHERE repository=? AND builder_subject_id=? AND builder_instance_id=? AND candidate_scope_digest=? AND resource_scope_digest=? AND capability_class=? ORDER BY record_json",(repository,builder_subject_id,builder_instance_id,candidate_scope_digest,resource_scope_digest,capability_class)).fetchall()
        return tuple(_decode_record(x[0]) for x in rows)
    def lookup_builder_process_runtime_provider_exact(self,*,provider_id,process_profile_digest,launch_policy_digest,capability_class):
        with self._lock,self._connect() as c:rows=c.execute("SELECT record_json FROM builder_process_runtime_provider WHERE provider_id=? AND process_profile_digest=? AND launch_policy_digest=? AND capability_class=? ORDER BY record_json",(provider_id,process_profile_digest,launch_policy_digest,capability_class)).fetchall()
        return tuple(_decode_record(x[0]) for x in rows)
    def ready(self):
        try:
            with self._connect() as c:names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return {"pr_bootstrap","authority_lineage","builder_subject","builder_process_runtime_provider"}.issubset(names)
        except Exception:return False

class PinnedBuilderProcessRuntimeProviderSource:
    __slots__=("_store","_runtime_resolver")
    def __init__(self,store,*,runtime_resolver:Callable[[str],object]):
        if type(store) is not SQLiteTrustedControlPlaneStore or store.ready() is not True or not callable(runtime_resolver): raise TrustedControlPlaneProviderError("trusted runtime provider source unavailable")
        self._store=store;self._runtime_resolver=runtime_resolver
    def resolve_exact(self,*,provider_id,process_profile_digest,launch_policy_digest):
        from cyber_lion.contracts.builder_process_launch import BuilderProcessRuntimeProviderDescriptor,PROVIDER_CAPABILITY_CLASS,PREPARE_CAPABILITY_CLASS
        rows=self._store.lookup_builder_process_runtime_provider_exact(provider_id=provider_id,process_profile_digest=process_profile_digest,launch_policy_digest=launch_policy_digest,capability_class=PROVIDER_CAPABILITY_CLASS)
        if len(rows)!=1: raise TrustedControlPlaneProviderError("runtime provider record missing or ambiguous")
        record=rows[0];payload=record.get("provider")
        if record.get("record_kind")!="builder-process-runtime-provider" or not isinstance(payload,Mapping): raise TrustedControlPlaneProviderError("runtime provider record invalid")
        try:d=BuilderProcessRuntimeProviderDescriptor(**dict(payload)).validate()
        except Exception as exc: raise TrustedControlPlaneProviderError("runtime provider descriptor invalid") from exc
        expected={"provider_id":provider_id,"process_profile_digest":process_profile_digest,"launch_policy_digest":launch_policy_digest,"capability_class":PROVIDER_CAPABILITY_CLASS}
        if d.descriptor_digest!=d.compute_digest() or dict(record.get("lookup_key",{}))!=expected: raise TrustedControlPlaneProviderError("runtime provider binding invalid")
        if (d.provider_id,d.supported_process_profile_digest,d.supported_launch_policy_digest,d.capability_class,d.prepare_capability_class)!=(provider_id,process_profile_digest,launch_policy_digest,PROVIDER_CAPABILITY_CLASS,PREPARE_CAPABILITY_CLASS): raise TrustedControlPlaneProviderError("runtime provider semantic binding mismatch")
        return d
    def resolve_bound_runtime(self,*,provider_id,process_profile_digest,launch_policy_digest):
        d=self.resolve_exact(provider_id=provider_id,process_profile_digest=process_profile_digest,launch_policy_digest=launch_policy_digest)
        try:r=self._runtime_resolver(d.runtime_instance_identity)
        except Exception as exc: raise TrustedControlPlaneProviderError("runtime provider instance unavailable") from exc
        if r is None or getattr(r,"descriptor",None)!=d or getattr(r,"runtime_instance_identity",None)!=d.runtime_instance_identity: raise TrustedControlPlaneProviderError("runtime provider instance binding mismatch")
        for m in ("prepare_launch","observe_held","observe_gate","commit_start","observe_launch","freeze_or_kill"):
            if not callable(getattr(r,m,None)): raise TrustedControlPlaneProviderError("runtime provider executable capability invalid")
        return r

class TrustedSignatureVerifierAdapter(TrustedSignatureVerifier):
    def __init__(self,verifier,*,ready=None):
        if not callable(verifier) or (ready is not None and not callable(ready)): raise TrustedControlPlaneProviderError("verifier invalid")
        self._verifier=verifier;self._ready=ready
    def verify(self,payload,signature,key_id,algorithm):
        try:r=self._verifier(payload,signature,key_id,algorithm)
        except Exception as exc: raise TrustedControlPlaneProviderError("signature backend failed closed") from exc
        if type(r) is not bool: raise TrustedControlPlaneProviderError("signature backend returned non-boolean result")
        return r
    def ready(self):
        if self._ready is None:return True
        try:return self._ready() is True
        except Exception:return False
