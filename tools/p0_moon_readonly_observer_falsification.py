from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json,os,sqlite3,stat
from typing import Callable,Tuple
from urllib.parse import quote

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from tools.p0_moon_readonly_observer_falsification_contract import (
    ATTACK_IDS,MoonBoundedFalsificationRuntimeSpec,MoonFenceObservationReceipt,
    MoonFenceReadback,MoonFutureAttackPlan,MoonObserverRuntimeCandidatePlan,MoonReadOnlyObserverSpec,
)
from tools.p0_moon_seven_binding import DIRECT_OBSERVER_BLOCKED,FENCE,PERMISSION

EXPECTED_SCAN_DIGEST="d345e96fb1c7c8c4c1ee9bea5672b64d51f290ce7129c860dbf97a5a7907cae2"
FENCE_PATH="/home/d2j3/.lion-moon-file-write-fence.sqlite3"
TARGET_PATH="/home/d2j3/lion-p0-moon-replace-live-cert-r1.canary"
TABLE="moon_file_write_effect"
OBSERVER_ID="moon-fence-readonly-observer-v1"
EXPECTED_COLUMNS=("effect_key","admission_digest","request_digest","repository","target_path","state","prepared_at","attempted_at","observed_at","reconciled_at","pre_observation_digest","post_observation_digest","reconciliation_digest")
EXPECTED_PK=("effect_key",)
EXPECTED_UNIQUE=("admission_digest","request_digest")
LIVE_REFS=("github-actions-run:33911284689","github-actions-job:101148041371","moon-reconciliation-digest:6648aeb323c104946ec91e5e2af4c53282f01561ed4dce2d7867775c0812819e")

class MoonObserverRuntimeError(RuntimeError):pass

def _canon(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _d(domain,value):return sha256(domain+b"\0"+_canon(value)).hexdigest()

class MoonFenceReadOnlyObserverCandidate:
    def __init__(self,*,connect_factory:Callable=sqlite3.connect,stat_factory:Callable=os.lstat):
        self._connect_factory=connect_factory;self._stat_factory=stat_factory
    @staticmethod
    def spec(parent_revision:str)->MoonReadOnlyObserverSpec:
        return MoonReadOnlyObserverSpec(parent_revision,FENCE_PATH,OBSERVER_ID,True,True,True,True,True,True,False,False,False,False,False,"CANDIDATE_UNATTACHED").validate()
    def _connect_readonly(self):
        uri="file:"+quote(FENCE_PATH,safe="/")+"?mode=ro"
        c=self._connect_factory(uri,uri=True,timeout=5,isolation_level=None,check_same_thread=False)
        c.execute("PRAGMA query_only=ON")
        row=c.execute("PRAGMA query_only").fetchone()
        if row is None or int(row[0])!=1:
            c.close();raise MoonObserverRuntimeError("query_only enforcement failed")
        return c
    @staticmethod
    def _inspect_connection(c,database_path:str,database_device:int,database_inode:int)->MoonFenceReadback:
        query_only=int(c.execute("PRAGMA query_only").fetchone()[0])==1
        rows=c.execute(f"PRAGMA table_info({TABLE})").fetchall()
        columns=tuple(str(r[1]) for r in rows)
        pk=tuple(str(r[1]) for r in sorted(rows,key=lambda r:int(r[5])) if int(r[5])>0)
        unique=[]
        for idx in c.execute(f"PRAGMA index_list({TABLE})").fetchall():
            if int(idx[2])!=1:continue
            cols=tuple(str(r[2]) for r in c.execute(f"PRAGMA index_info({idx[1]})").fetchall())
            if len(cols)==1:unique.append(cols[0])
        unique=tuple(sorted(set(unique)))
        schema_sql_row=c.execute("SELECT sql FROM sqlite_schema WHERE type='table' AND name=?",(TABLE,)).fetchone()
        schema_sql="" if schema_sql_row is None or schema_sql_row[0] is None else str(schema_sql_row[0])
        journal=str(c.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        synchronous=int(c.execute("PRAGMA synchronous").fetchone()[0])
        schema_payload={"table":TABLE,"columns":columns,"primary_key":pk,"unique_columns":unique,"schema_sql":schema_sql}
        pragma_payload={"journal_mode":journal,"synchronous":synchronous,"query_only":query_only}
        return MoonFenceReadback(
            database_path,database_device,database_inode,query_only,TABLE,columns,pk,unique,journal,synchronous,
            _d(b"LION/MOON-FENCE-SCHEMA-STATE/1",schema_payload),_d(b"LION/MOON-FENCE-PRAGMA-STATE/1",pragma_payload),
            columns==EXPECTED_COLUMNS and pk==EXPECTED_PK and set(EXPECTED_UNIQUE).issubset(set(unique)),journal=="wal",synchronous==2,False,
        ).validate()
    def inspect(self)->MoonFenceReadback:
        before=self._stat_factory(FENCE_PATH)
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):raise MoonObserverRuntimeError("fence database identity unsafe")
        c=self._connect_readonly()
        try:readback=self._inspect_connection(c,FENCE_PATH,int(before.st_dev),int(before.st_ino))
        finally:c.close()
        after=self._stat_factory(FENCE_PATH)
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):raise MoonObserverRuntimeError("database identity changed during readback")
        if not readback.schema_exact:raise MoonObserverRuntimeError("fence schema mismatch")
        if not readback.journal_mode_exact:raise MoonObserverRuntimeError("journal_mode mismatch")
        if not readback.synchronous_value_exact:raise MoonObserverRuntimeError("synchronous readback mismatch")
        return readback
    @staticmethod
    def seal_live_receipt(*,revision:str,tree:str,readback:MoonFenceReadback,observed_at:str,live_observation:bool)->MoonFenceObservationReceipt:
        if not live_observation:raise MoonObserverRuntimeError("live observation receipt cannot be fabricated")
        readback.validate()
        return MoonFenceObservationReceipt(revision,tree,readback.database_path,f"{readback.database_device}:{readback.database_inode}",True,readback.schema_digest,readback.pragma_digest,OBSERVER_ID,observed_at,readback.digest()).sealed()

class MoonBoundedFalsificationRuntimeCandidate:
    def __init__(self,parent_revision:str):self.parent_revision=parent_revision
    @staticmethod
    def _rows():
        fence=tuple(sorted(FENCE));permission=(PERMISSION,)
        return {
            "WRONG_EXPECTED_STATE":(fence,"MoonFileWriteRequest.validate","REPLACE_EXPECTED_DIGEST requires exact pre-state"),
            "REPLAYED_EFFECT_KEY":(fence,"DurableMoonFileWriteFence.prepare","durable file-write replay denied"),
            "REPOSITORY_SUBSTITUTION":(permission,"MoonFileWriteRequest.validate","fixed execution context mismatch"),
            "ACTOR_SUBSTITUTION":(permission,"MoonFileWriteRequest.validate","actor_login invalid"),
            "CONTROL_ISSUE_SUBSTITUTION":(permission,"MoonFileWriteRequest.validate","fixed execution context mismatch"),
        }
    def plan(self,attack_id:str,*,target_path:str=TARGET_PATH,fence_path:str=FENCE_PATH,command=None)->MoonFutureAttackPlan:
        if attack_id not in ATTACK_IDS:raise MoonObserverRuntimeError("unknown attack id")
        if target_path!=TARGET_PATH or fence_path!=FENCE_PATH:raise MoonObserverRuntimeError("arbitrary path denied")
        if command is not None:raise MoonObserverRuntimeError("arbitrary command denied")
        surfaces,pep,denial=self._rows()[attack_id]
        refs=LIVE_REFS+(f"source-pep:{pep}","candidate-no-live-execution")
        return MoonFutureAttackPlan(attack_id,surfaces,pep,denial,True,True,False,TARGET_PATH,FENCE_PATH,True,False,"CANDIDATE_UNEXECUTED",refs).validate()
    def spec(self)->MoonBoundedFalsificationRuntimeSpec:
        plans=tuple(self.plan(a) for a in ATTACK_IDS)
        return MoonBoundedFalsificationRuntimeSpec(self.parent_revision,144,24,"LION-AUTH-LAB",TARGET_PATH,FENCE_PATH,ATTACK_IDS,tuple(p.digest() for p in plans),False,False,False,False,False,False,False,False,False,"CANDIDATE_UNATTACHED").validate()
    def execute(self,*args,**kwargs):raise MoonObserverRuntimeError("live falsification disabled in candidate")

@dataclass(frozen=True)
class MoonObserverRuntimeArtifacts:
    observer_spec:MoonReadOnlyObserverSpec
    runtime_spec:MoonBoundedFalsificationRuntimeSpec
    attack_plans:Tuple[MoonFutureAttackPlan,...]
    plan:MoonObserverRuntimeCandidatePlan

def materialize_observer_runtime(*,inventory:EffectSurfaceInventory)->MoonObserverRuntimeArtifacts:
    inventory.validate()
    if inventory.scan_digest!=EXPECTED_SCAN_DIGEST:raise MoonObserverRuntimeError("production scan digest drift")
    known={s.digest() for s in inventory.surfaces}
    if set(DIRECT_OBSERVER_BLOCKED)-known:raise MoonObserverRuntimeError("blocked surface drift")
    observer=MoonFenceReadOnlyObserverCandidate.spec(inventory.revision)
    runtime=MoonBoundedFalsificationRuntimeCandidate(inventory.revision)
    attacks=tuple(runtime.plan(a) for a in ATTACK_IDS)
    runtime_spec=runtime.spec()
    plan=MoonObserverRuntimeCandidatePlan(inventory.digest(),inventory.scan_digest,observer.digest(),runtime_spec.digest(),tuple(sorted(DIRECT_OBSERVER_BLOCKED)),tuple(a.digest() for a in attacks),0,0,False,False,"UNKNOWN",LIVE_REFS+("synchronous-historical-proof:requires-same-connection-instrumentation",)).validate()
    return MoonObserverRuntimeArtifacts(observer,runtime_spec,attacks,plan)
