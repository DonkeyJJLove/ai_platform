from __future__ import annotations
from dataclasses import dataclass,replace
from hashlib import sha256
import ast,json,subprocess
from pathlib import Path
from typing import Mapping,Tuple

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from cyber_lion.contracts.mediation_falsification import BypassFalsificationResult,MediationBindingCandidate
from cyber_lion.enterprise.mediation_falsification import MediationBindingRegistry,SurfaceBindingResolver
from cyber_lion.enterprise.production_mediation import MediationChainReconstructor,ProductionEffectInventory
from tools.p0_moon_attack_registry import ATTACKS,FENCE_SURFACES,LIVE_ATTACK_IDS,PERMISSION_SURFACE,PREPARED_SURFACE,attack
from tools.p0_moon_runner_attested_bridge_contract import RunnerAttestedOperationReceipt
from tools.p0_moon_seven_binding import materialize_seven,certified_runtime_evidence
from tools.p0_moon_seven_binding_contract import MoonEvidenceComponent,MoonSurfaceEvidenceBundle
from tools.p0_moon_attested_adjudication_contract import (
    AttestedAdjudicationContractError,AttestedAdjudicationPlan,AttestedVerifierIdentity,CanonicalAttackDefinition,
    CanonicalAttackPepIdentity,GitHubJobEvidence,GitHubRunEvidence,MediationAttackRequirement,MediationAttackRequirementPolicy,
    ObservationReconciliationRule,RevisionRebindProof,RunnerAttestedAdjudicationRecord,SourceSemanticContinuityProof,
)

SOURCE_REVISION="830f8c2e5561655dc35118c97f4574acc3bf0816"
SOURCE_TREE="5189c1a582400de829f08c4103fdfafa993ba2e6"
SOURCE_INVENTORY="a87e0f9ccb4fb81bbbc168900a8db8984f554a74a0b3f8c2a637d75e85fcb9df"
EXPECTED_SCAN_DIGEST="cf13b4c46d1c77a58a2d9ee4d839a4994aa18ff126713886bc5e62649b998c18"
SOURCE_BRIDGE_BLOB="a5ec373145f01ae2713fa620baa9799819cb813a"
WORKFLOW_PATH=".github/workflows/lion-moon-runner-attested-execution-bridge.yml"
WORKFLOW_REF="DonkeyJJLove/ai_platform/.github/workflows/lion-moon-runner-attested-execution-bridge.yml@refs/heads/mission/p0-moon-runner-attested-execution-bridge-attach-r1"
SOURCE_BLOBS={
    "cyber_lion/contracts/moon_file_write.py":"bfa4c65de626e3dacf8dd20cb41703fea88d8dc5",
    "cyber_lion/enterprise/moon_file_write.py":"ebc407df90b4bf7311e901ffeb6d389ad26efd36",
    "cyber_lion/enterprise/moon_file_write_mediation.py":"2d4e704cf6143893141cdaae1d0810e50d874522",
    "cyber_lion/enterprise/mediation_falsification.py":"3b972df80ecacbd8198d060a860cf4063d62e2e3",
    "tools/p0_moon_runner_attested_execution_bridge.py":SOURCE_BRIDGE_BLOB,
}
SOURCE_SEMANTIC_ANCHORS={
    ("cyber_lion/enterprise/moon_file_write.py","function","_github_permission"):"a5b3c38ea1be59b35dbdab6ba09a898d0cc803f04b09eb055d20f0a96cbe1a31",
    ("cyber_lion/enterprise/moon_file_write.py","class","ExactMoonFileWriteEffectProvider"):"479a4f7d199bf95581ba4fc67a99d2019c7d377589120cc0d55fb8daa1dcc502",
    ("cyber_lion/enterprise/moon_file_write_mediation.py","class","DurableMoonFileWriteFence"):"193019a30ab776df81a7be2069d8e2a210212111ce2e0a0f179068488943b642",
    ("cyber_lion/enterprise/moon_file_write_mediation.py","class","MoonFileWriteObserver"):"9899f2d0fee3e710e3a169157d0c243e6ce3ec1e33531a563edcb126954066f5",
}
CREATE_TABLE_SURFACE="478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d"
PRAGMA_SURFACE="e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0"
OBSERVATION_MAP={"OBSERVE_SCHEMA":CREATE_TABLE_SURFACE,"OBSERVE_SAME_CONNECTION_PRAGMA":PRAGMA_SURFACE}
POLICY_VERSION="MOON-MEDIATION-ATTACK-POLICY/1"
EPOCH_PREFIX="P0-MOON-ATTESTED-ADJ-R1@"

# Literal outer receipts reacquired from GitHub Actions job logs.  The inner receipt payloads are intentionally absent.
_OUTER={
"OBSERVE_SCHEMA":dict(attestation_digest="999fb8a6a441b159668142b4a500ec1541ab176fa75426cd1a4f40950ea5f43d",run_id="33927134326",job_id="execute-operation",workflow_ref=WORKFLOW_REF,revision=SOURCE_REVISION,tree=SOURCE_TREE,runner_name="lion-moon-r9d8-test",runner_agent_id=24,os_user="lion-maintenance-runner",uid=993,hostname="LION-AUTH-LAB",machine_id="e69aa593257d47b8885d1bd87710b196",operation="OBSERVE_SCHEMA",result="OBSERVED",result_digest="2065f97c69a0564a41df5c0f8fb9d1f11af88e31e98faed477c1bfda6d8574e7",observed_at="2026-09-04T22:50:12.192946+00:00",receipt_digest="1791c38dae3572f8d8ed0b54aa86a996b75f892c6079efb75fd8b9354bf043e2"),
"OBSERVE_SAME_CONNECTION_PRAGMA":dict(attestation_digest="bb76fe7a8db7e15792ec681e12b1dbea304d0bbcb25995aa7ee7feef47a91246",run_id="33927211665",job_id="execute-operation",workflow_ref=WORKFLOW_REF,revision=SOURCE_REVISION,tree=SOURCE_TREE,runner_name="lion-moon-r9d8-test",runner_agent_id=24,os_user="lion-maintenance-runner",uid=993,hostname="LION-AUTH-LAB",machine_id="e69aa593257d47b8885d1bd87710b196",operation="OBSERVE_SAME_CONNECTION_PRAGMA",result="OBSERVED",result_digest="7a7a831aaeef74e58923a1dfecd7afd39a49febd68bc31b1faf86151ee45a684",observed_at="2026-09-04T22:51:19.627789+00:00",receipt_digest="0d63f270fb15e0ee3b530a0ca3a6dbfbb915cebc3fae061bdc0167a3d545368e"),
"DENY_WRONG_EXPECTED_STATE":dict(attestation_digest="8748ed998da4692153b09643b54946d54b4d2c5d65f0198ebda6dfbe951d1b57",run_id="33927255382",job_id="execute-operation",workflow_ref=WORKFLOW_REF,revision=SOURCE_REVISION,tree=SOURCE_TREE,runner_name="lion-moon-r9d8-test",runner_agent_id=24,os_user="lion-maintenance-runner",uid=993,hostname="LION-AUTH-LAB",machine_id="e69aa593257d47b8885d1bd87710b196",operation="DENY_WRONG_EXPECTED_STATE",result="DENIED",result_digest="4b28286af696bbb501a136f1eeb1a5c9b5f292285932a53f47c3735e3f11a9fa",observed_at="2026-09-04T22:51:58.578554+00:00",receipt_digest="79e775642634753f2cd3206ed512b6ecc056ea2419132e012e71341f32da3d19"),
"DENY_REPLAYED_EFFECT_KEY":dict(attestation_digest="5e3bc2acf81c99034096d91b81e0207188cd9fefa147fa5ababebfc1c09a7fcb",run_id="33927302068",job_id="execute-operation",workflow_ref=WORKFLOW_REF,revision=SOURCE_REVISION,tree=SOURCE_TREE,runner_name="lion-moon-r9d8-test",runner_agent_id=24,os_user="lion-maintenance-runner",uid=993,hostname="LION-AUTH-LAB",machine_id="e69aa593257d47b8885d1bd87710b196",operation="DENY_REPLAYED_EFFECT_KEY",result="DENIED",result_digest="0efc5bfcbb573643b9fc2e7bbda9f9aeed9be8a56dafe3a9c1e7f2ca94bf41ec",observed_at="2026-09-04T22:52:41.006276+00:00",receipt_digest="bb572e0dd83864dead4691caffdc243bccf9818e572b0a463115185489d3e64b"),
"DENY_REPOSITORY_SUBSTITUTION":dict(attestation_digest="6bc54012c7865c94b6a9a27a8acc3008d7b312b49802fcf3b89c15fb2c0979ed",run_id="33927345065",job_id="execute-operation",workflow_ref=WORKFLOW_REF,revision=SOURCE_REVISION,tree=SOURCE_TREE,runner_name="lion-moon-r9d8-test",runner_agent_id=24,os_user="lion-maintenance-runner",uid=993,hostname="LION-AUTH-LAB",machine_id="e69aa593257d47b8885d1bd87710b196",operation="DENY_REPOSITORY_SUBSTITUTION",result="DENIED",result_digest="e38f9114ebbd14641207cebf6ba5fc612b714615c768864cbfbed6b72fdbb559",observed_at="2026-09-04T22:53:18.510803+00:00",receipt_digest="649b4f698aecf00b72aa4c5f174201ec2b89765976078972f78beb774adcbf3c"),
"DENY_ACTOR_SUBSTITUTION":dict(attestation_digest="fc097b20d3be81bffd31e55d04f571a6ff72d1a0b54b20db6ebe07c3e4fd7617",run_id="33927388123",job_id="execute-operation",workflow_ref=WORKFLOW_REF,revision=SOURCE_REVISION,tree=SOURCE_TREE,runner_name="lion-moon-r9d8-test",runner_agent_id=24,os_user="lion-maintenance-runner",uid=993,hostname="LION-AUTH-LAB",machine_id="e69aa593257d47b8885d1bd87710b196",operation="DENY_ACTOR_SUBSTITUTION",result="DENIED",result_digest="ae15a5bb02bc40b296e19f9882df8497662043a4dbe31b0d68ce9fd0fce8b2f3",observed_at="2026-09-04T22:53:59.609159+00:00",receipt_digest="5f9194e6b9a0ee92468e5157567c8a686a448508adbc861e6b7073193ea0045e"),
"DENY_CONTROL_ISSUE_SUBSTITUTION":dict(attestation_digest="6c3f970527dc3a5066357ba8946070c1b4a45edeeb78d00701b6b2b305ca721f",run_id="33927452740",job_id="execute-operation",workflow_ref=WORKFLOW_REF,revision=SOURCE_REVISION,tree=SOURCE_TREE,runner_name="lion-moon-r9d8-test",runner_agent_id=24,os_user="lion-maintenance-runner",uid=993,hostname="LION-AUTH-LAB",machine_id="e69aa593257d47b8885d1bd87710b196",operation="DENY_CONTROL_ISSUE_SUBSTITUTION",result="DENIED",result_digest="6574aa2c99313237a1fa55cfd8157d23828e4caa44cb9053248526335b24a71e",observed_at="2026-09-04T22:54:58.573036+00:00",receipt_digest="76eb43bb2a6c166d1ee3e16b22125feea90f9267bd9b84bae120c46017efe849"),
}
_NUMERIC_JOBS={"OBSERVE_SCHEMA":101197998069,"OBSERVE_SAME_CONNECTION_PRAGMA":101198227837,"DENY_WRONG_EXPECTED_STATE":101198355162,"DENY_REPLAYED_EFFECT_KEY":101198492105,"DENY_REPOSITORY_SUBSTITUTION":101198618910,"DENY_ACTOR_SUBSTITUTION":101198749138,"DENY_CONTROL_ISSUE_SUBSTITUTION":101198939862}

def _outer(operation:str)->RunnerAttestedOperationReceipt:return RunnerAttestedOperationReceipt(**_OUTER[operation]).validate()
def _run(operation:str)->GitHubRunEvidence:
    o=_outer(operation);return GitHubRunEvidence(int(o.run_id),"workflow_dispatch","completed","success",SOURCE_REVISION,SOURCE_TREE,WORKFLOW_PATH,"mission/p0-moon-runner-attested-execution-bridge-attach-r1").validate()
def _job(operation:str)->GitHubJobEvidence:
    o=_outer(operation);return GitHubJobEvidence(_NUMERIC_JOBS[operation],int(o.run_id),"execute-operation","completed","success","lion-moon-r9d8-test",24).validate()

class AttestedAdjudicationError(RuntimeError):pass

_AST_V2_DOMAIN=b"LION/MOON-SOURCE-SEMANTIC-AST/2\0"
_AST_V2_NODES=frozenset("Add And AnnAssign Assign Attribute AugAssign BinOp BitOr BoolOp Break Call ClassDef Compare Constant Dict Eq ExceptHandler Expr FormattedValue FunctionDef GeneratorExp Gt If IfExp Is IsNot JoinedStr Load LtE Name Not NotEq Or Pass Raise Return Slice Starred Store Subscript Try Tuple UnaryOp While With arg arguments comprehension keyword withitem".split())
_AST_V2_FIELDS=frozenset("annotation arg args attr bases body cause comparators context_expr conversion ctx decorator_list defaults elt elts exc finalbody format_spec func generators handlers id ifs is_async items iter keys keywords kind kw_defaults kwarg kwonlyargs left lower name op operand ops optional_vars orelse posonlyargs returns right simple slice step target targets test type type_comment upper value values vararg".split())

def _empty_ast_schema_extension(value)->bool:
    return value is None or value==[] or value==()

def _canonical_ast_scalar(value):
    if value is None:return {"type":"none"}
    if value is Ellipsis:return {"type":"ellipsis"}
    if type(value) is bool:return {"type":"bool","value":value}
    if type(value) is int:return {"type":"int","value":str(value)}
    if type(value) is str:return {"type":"str","value":value}
    if type(value) is bytes:return {"type":"bytes","value":value.hex()}
    raise AttestedAdjudicationError(f"unsupported AST scalar: {type(value).__name__}")

def _canonical_ast_value(value):
    if isinstance(value,ast.AST):return _canonical_ast_node(value)
    if isinstance(value,list):return {"type":"list","items":[_canonical_ast_value(x) for x in value]}
    if isinstance(value,tuple):return {"type":"tuple","items":[_canonical_ast_value(x) for x in value]}
    return _canonical_ast_scalar(value)

def _canonical_ast_node(node:ast.AST):
    node_type=type(node).__name__
    if node_type not in _AST_V2_NODES:raise AttestedAdjudicationError(f"unsupported AST node: {node_type}")
    runtime_fields=getattr(node,"_fields",None)
    if type(runtime_fields) is not tuple:raise AttestedAdjudicationError(f"AST schema fields unavailable: {node_type}")
    fields={}
    for field in runtime_fields:
        try:value=getattr(node,field)
        except AttributeError as exc:raise AttestedAdjudicationError(f"AST schema field missing: {node_type}:{field}") from exc
        if field not in _AST_V2_FIELDS:
            if _empty_ast_schema_extension(value):continue
            raise AttestedAdjudicationError(f"unknown non-empty AST field: {node_type}:{field}")
        fields[field]=_canonical_ast_value(value)
    return {"node":node_type,"fields":fields}

class RunnerAttestedReceiptAdjudicator:
    def adjudicate(self,*,outer:RunnerAttestedOperationReceipt,run:GitHubRunEvidence,job:GitHubJobEvidence,source_bridge_blob_sha:str=SOURCE_BRIDGE_BLOB)->RunnerAttestedAdjudicationRecord:
        outer.validate();run.validate();job.validate()
        # Explicit digest recomputation, not trust in the printed digest.
        resealed=RunnerAttestedOperationReceipt(**outer.payload()).sealed()
        if resealed.receipt_digest!=outer.receipt_digest:raise AttestedAdjudicationError("outer receipt digest mismatch")
        if int(outer.run_id)!=run.run_id_numeric or job.run_id_numeric!=run.run_id_numeric:raise AttestedAdjudicationError("run binding mismatch")
        if outer.job_id!=job.job_name:raise AttestedAdjudicationError("job name binding mismatch")
        if (run.head_sha,run.head_tree)!=(outer.revision,outer.tree):raise AttestedAdjudicationError("run revision/tree mismatch")
        if (job.runner_name,job.runner_agent_id)!=(outer.runner_name,outer.runner_agent_id):raise AttestedAdjudicationError("runner binding mismatch")
        if source_bridge_blob_sha!=SOURCE_BRIDGE_BLOB:raise AttestedAdjudicationError("source bridge substitution")
        refs=(f"github-actions-run:{run.run_id_numeric}",f"github-actions-job:{job.job_id_numeric}",f"outer-receipt:{outer.receipt_digest}",f"inner-result:{outer.result_digest}",f"source-bridge-blob:{source_bridge_blob_sha}")
        return RunnerAttestedAdjudicationRecord(run.run_id_numeric,job.job_id_numeric,job.job_name,outer.attestation_digest,outer.receipt_digest,outer.result_digest,outer.operation,outer.result,outer.revision,outer.tree,outer.runner_name,outer.runner_agent_id,outer.os_user,outer.uid,outer.hostname,outer.machine_id,outer.workflow_ref,source_bridge_blob_sha,outer.observed_at,refs).sealed()

def adjudicate_live_receipts()->Mapping[str,RunnerAttestedAdjudicationRecord]:
    a=RunnerAttestedReceiptAdjudicator();return {op:a.adjudicate(outer=_outer(op),run=_run(op),job=_job(op)) for op in _OUTER}

def _git_blob(root:Path,path:str)->str:
    return subprocess.run(["git","hash-object",path],cwd=root,text=True,stdout=subprocess.PIPE,check=True).stdout.strip()
def _node(source:str,kind,name:str):
    tree=ast.parse(source)
    if kind=="class":cls=ast.ClassDef
    elif kind=="function":cls=ast.FunctionDef
    else:raise AttestedAdjudicationError(f"semantic continuity node kind unsupported: {kind}")
    matches=[node for node in tree.body if isinstance(node,cls) and node.name==name]
    if not matches:raise AttestedAdjudicationError(f"semantic continuity node absent: {kind}:{name}")
    if len(matches)!=1:raise AttestedAdjudicationError(f"semantic continuity node ambiguous: {kind}:{name}")
    return matches[0]
def _ast_digest(source:str,kind:str,name:str)->str:
    canonical=_canonical_ast_node(_node(source,kind,name))
    try:payload=json.dumps(canonical,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    except (TypeError,ValueError,UnicodeError) as exc:raise AttestedAdjudicationError("semantic continuity canonical serialization failed") from exc
    return sha256(_AST_V2_DOMAIN+payload).hexdigest()
def _require_semantic_anchor(source:str,path:str,kind:str,name:str)->None:
    expected=SOURCE_SEMANTIC_ANCHORS[(path,kind,name)]
    if _ast_digest(source,kind,name)!=expected:
        raise AttestedAdjudicationError(f"semantic continuity anchor drift: {path}:{kind}:{name}")
def source_semantic_continuity_proofs(*,inventory:EffectSurfaceInventory,repo_root:Path)->Tuple[SourceSemanticContinuityProof,...]:
    inventory.validate();out=[]
    provider="cyber_lion/enterprise/moon_file_write.py";mediation="cyber_lion/enterprise/moon_file_write_mediation.py"
    new_provider=(repo_root/provider).read_text();old_pb=SOURCE_BLOBS[provider];new_pb=_git_blob(repo_root,provider)
    if new_pb==old_pb:raise AttestedAdjudicationError("provider semantic change proof expected changed blob")
    _require_semantic_anchor(new_provider,provider,"function","_github_permission")
    _require_semantic_anchor(new_provider,provider,"class","ExactMoonFileWriteEffectProvider")
    if 'TRUSTED_PERMISSIONS = {"admin", "maintain", "write"}' not in new_provider or 'raise MoonFileWriteMediationError("actor permission is not trusted")' not in new_provider:raise AttestedAdjudicationError("trusted permission semantics changed")
    if new_provider.splitlines()[119].strip()!='connection.request("GET", path, headers=headers)' or 'os.replace(' not in new_provider.splitlines()[314]:raise AttestedAdjudicationError("provider effect entrypoint line identity drift")
    resolver=new_provider[new_provider.index('    def resolve(self, request: MoonFileWriteRequest)'):new_provider.index('\n\n\nclass ExactMoonFileWriteEffectProvider')];i_subject=resolver.index('authority subject substitution');i_obs=resolver.index('_github_permission(');i_decision=resolver.index('_require_trusted_permission(permission)');i_source=resolver.index('authority_source_digest =')
    if not i_subject<i_obs<i_decision<i_source:raise AttestedAdjudicationError("permission refactor control flow drift")
    out.append(SourceSemanticContinuityProof(provider,old_pb,new_pb,SOURCE_REVISION,inventory.revision,("_github_permission AST unchanged","ExactMoonFileWriteEffectProvider AST unchanged","trusted permission set unchanged","connection.request remains line 120","os.replace remains line 315","repository/actor substitution remains before authority observation"),("pure _require_trusted_permission boundary introduced after authority observation",),(f"source-live:{provider}@{old_pb}",f"source-live-ast-anchor:{SOURCE_SEMANTIC_ANCHORS[(provider,'function','_github_permission')]}",f"source-live-ast-anchor:{SOURCE_SEMANTIC_ANCHORS[(provider,'class','ExactMoonFileWriteEffectProvider')]}",f"source-current:{provider}@{new_pb}","no-effect-provider-change")).validate())
    new_med=(repo_root/mediation).read_text();old_mb=SOURCE_BLOBS[mediation];new_mb=_git_blob(repo_root,mediation)
    if new_mb==old_mb:raise AttestedAdjudicationError("mediation semantic change proof expected changed blob")
    for cls in ("DurableMoonFileWriteFence","MoonFileWriteObserver"):
        _require_semantic_anchor(new_med,mediation,"class",cls)
    lines=new_med.splitlines()
    if 'c.execute("INSERT INTO moon_file_write_effect' not in lines[305] or 'self.fence.prepare(' not in lines[434] or 'self.fence.mark_attempted(' not in lines[443] or 'self.effect.write_exact(' not in lines[444]:raise AttestedAdjudicationError("mediation effect entrypoint line identity drift")
    execute=new_med[new_med.index('    def execute(self, request: MoonFileWriteRequest)'):new_med.index('\n\ndef _require_current_admission')];i_pre=execute.index('pre_fence_admission = self.admissions.resolve(request)');i_precheck=execute.index('_require_current_admission(admission, pre_fence_admission)');i_prepare=execute.index('self.fence.prepare(');i_post=execute.index('current_admission = self.admissions.resolve(request)');i_postcheck=execute.index('_require_current_admission(admission, current_admission)');i_attempt=execute.index('self.fence.mark_attempted(');i_effect=execute.index('self.effect.write_exact(')
    if not i_pre<i_precheck<i_prepare<i_post<i_postcheck<i_attempt<i_effect:raise AttestedAdjudicationError("authority currentness strengthened order drift")
    helper=new_med[new_med.index('def _require_current_admission('):]
    if 'current.admission_digest != baseline.admission_digest' not in helper or 'raise MoonFileWriteMediationError("authority drift")' not in helper:raise AttestedAdjudicationError("pure currentness comparator semantics drift")
    out.append(SourceSemanticContinuityProof(mediation,old_mb,new_mb,SOURCE_REVISION,inventory.revision,("DurableMoonFileWriteFence AST unchanged","MoonFileWriteObserver AST unchanged","fence INSERT remains line 306","fence.prepare call remains line 435","mark_attempted remains line 444","effect.write_exact remains line 445","post-prepare authority revalidation preserved"),("pre-fence authority revalidation added before durable state","pure admission-digest currentness comparator introduced"),(f"source-live:{mediation}@{old_mb}",f"source-live-ast-anchor:{SOURCE_SEMANTIC_ANCHORS[(mediation,'class','DurableMoonFileWriteFence')]}",f"source-live-ast-anchor:{SOURCE_SEMANTIC_ANCHORS[(mediation,'class','MoonFileWriteObserver')]}",f"source-current:{mediation}@{new_mb}","post-prepare-toctou-defence-preserved")).validate())
    return tuple(out)
def revision_rebind_proof(*,inventory:EffectSurfaceInventory,repo_root:Path)->RevisionRebindProof:
    inventory.validate()
    if inventory.scan_digest!=EXPECTED_SCAN_DIGEST:raise AttestedAdjudicationError("scan digest drift")
    changed={"cyber_lion/enterprise/moon_file_write.py","cyber_lion/enterprise/moon_file_write_mediation.py"};unchanged=[]
    for path,expected in SOURCE_BLOBS.items():
        got=_git_blob(repo_root,path)
        if path in changed:
            if got==expected:raise AttestedAdjudicationError(f"expected explicit changed source blob: {path}")
            continue
        if got!=expected:raise AttestedAdjudicationError(f"unexpected source blob drift: {path}")
        unchanged.append(f"{path}@{got}")
    proofs=source_semantic_continuity_proofs(inventory=inventory,repo_root=repo_root)
    if {x.source_path for x in proofs}!=changed:raise AttestedAdjudicationError("changed source semantic proof set drift")
    refs=("source-live-revision:"+SOURCE_REVISION,"target-candidate-revision:"+inventory.revision)+tuple(f"semantic-continuity:{x.digest()}" for x in proofs)
    return RevisionRebindProof(SOURCE_REVISION,SOURCE_TREE,SOURCE_INVENTORY,inventory.revision,inventory.tree_digest,inventory.digest(),inventory.scan_digest,tuple(sorted(unchanged)),tuple(sorted(x.digest() for x in proofs)),refs).validate()

def _pep_source(pep:str):
    if pep=="MoonFileWriteRequest.validate":return "cyber_lion/contracts/moon_file_write.py"
    if pep in {"DurableMoonFileWriteFence.get","DurableMoonFileWriteFence.prepare","CanonicalMoonFileWriteMediator.execute"}:return "cyber_lion/enterprise/moon_file_write_mediation.py"
    if pep=="_PermissionAdmissionResolver.resolve":return "cyber_lion/enterprise/moon_file_write.py"
    if pep in {"SurfaceBindingResolver.resolve","MediationBindingRegistry.register"}:return "cyber_lion/enterprise/mediation_falsification.py"
    raise AttestedAdjudicationError("unknown canonical PEP source: "+pep)
def _pep_digest(pep:str,revision:str):
    path=_pep_source(pep);return CanonicalAttackPepIdentity(pep,path,SOURCE_BLOBS[path],revision,"required-attack-pep").digest()

def canonical_attack_definitions(*,inventory:EffectSurfaceInventory,base_artifacts)->Tuple[CanonicalAttackDefinition,...]:
    out=[]
    for aid in ATTACKS:
        t=attack(aid)
        if aid in {"ACTOR_SUBSTITUTION","UNTRUSTED_PERMISSION"}:pep_digest=base_artifacts.bundles[PERMISSION_SURFACE].pep_identity_digest
        elif aid=="REPLAYED_EFFECT_KEY":pep_digest=base_artifacts.bundles[PREPARED_SURFACE].pep_identity_digest
        else:pep_digest=_pep_digest(t.pep,inventory.revision)
        out.append(CanonicalAttackDefinition(aid,t.surface_digests,t.pep,t.expected_denial,pep_digest,t.execution_class,t.conversion_rule,(f"source-pep:{_pep_source(t.pep)}",f"canonical-registry:{aid}")).validate())
    return tuple(out)

def attack_policy(*,inventory:EffectSurfaceInventory,definitions:Tuple[CanonicalAttackDefinition,...])->MediationAttackRequirementPolicy:
    defs={d.attack_id:d for d in definitions};struct=("SURFACE_SUBSTITUTION","PROVIDER_SUBSTITUTION","ENTRYPOINT_SUBSTITUTION","CROSS_EPOCH_BINDING")
    req=[]
    for sd in FENCE_SURFACES:
        ids=struct+(("REPLAYED_EFFECT_KEY",) if sd==PREPARED_SURFACE else ())
        req.append(MediationAttackRequirement(sd,ids,tuple("STRUCTURAL_EXACT" if a in struct else "SURFACE_EXACT" for a in ids),tuple(defs[a].expected_pep_digest for a in ids),"Binding substitution must be rejected for every fence surface; PREPARED additionally requires observed replay denial.",POLICY_VERSION).validate())
    pids=("REPOSITORY_SUBSTITUTION","ACTOR_SUBSTITUTION","CONTROL_ISSUE_SUBSTITUTION","UNTRUSTED_PERMISSION","STALE_AUTHORITY_SOURCE")
    req.append(MediationAttackRequirement(PERMISSION_SURFACE,pids,tuple("SURFACE_EXACT" for _ in pids),tuple(defs[a].expected_pep_digest for a in pids),"Authority observation requires exact context, actor, permission trust, and fresh authority evidence.",POLICY_VERSION).validate())
    return MediationAttackRequirementPolicy(inventory.digest(),inventory.revision,POLICY_VERSION,tuple(sorted(req,key=lambda x:x.surface_digest)),tuple(sorted(d.digest() for d in definitions)),("policy:explicit-nonempty-required-attacks","wrong-expected-state:family-evidence-only")).validate()

def _promote_component(c:MoonEvidenceComponent,record:RunnerAttestedAdjudicationRecord,model:str,**extra)->MoonEvidenceComponent:
    payload=dict(c.payload);payload.update({"model":model,"adjudication_digest":record.adjudication_digest,"outer_receipt_digest":record.outer_receipt_digest,"inner_result_digest":record.inner_result_digest});payload.update({k:str(v) for k,v in extra.items()})
    refs=tuple(dict.fromkeys(c.evidence_refs+record.evidence_refs+(f"adjudication:{record.adjudication_digest}",)))
    return MoonEvidenceComponent(c.component_type,c.subject,c.revision,tuple(sorted((str(k),str(v)) for k,v in payload.items())),refs,"OBSERVED").validate()

def _adjudicated_bundle(*,inventory,surface,base_artifacts,record:RunnerAttestedAdjudicationRecord):
    sd=surface.digest();comps=list(base_artifacts.components[sd]);new=[];rule=None
    for c in comps:
        payload=dict(c.payload);role=payload.get("role","")
        if c.component_type=="observer_identity" and role=="effect-readback":
            new.append(_promote_component(c,record,"runner-attested exact postcondition observer"));continue
        if c.component_type=="replay_guard":
            if sd==CREATE_TABLE_SURFACE:model="CREATE TABLE IF NOT EXISTS + exact live schema postcondition"
            else:model="idempotent WAL/FULL configuration + same-connection readback + stable database identity"
            new.append(_promote_component(c,record,model,replay_semantics="current-epoch-idempotence-not-historical-causality"));continue
        if c.component_type=="reconciliation_boundary":
            model="runner-attested current postcondition reconciliation; no historical causality claim"
            rule=ObservationReconciliationRule(sd,"MOON-OBSERVATION-RECONCILIATION/1",model,surface.entrypoints[0],record.adjudication_digest,record.inner_result_digest,False,(f"adjudication:{record.adjudication_digest}",f"inner-result:{record.inner_result_digest}")).validate()
            new.append(_promote_component(c,record,model,reconciliation_rule_digest=rule.digest(),historical_causality_claimed="false"));continue
        new.append(c)
    bytype={};
    for c in new:bytype.setdefault(c.component_type,[]).append(c)
    base=base_artifacts.bundles[sd]
    obs=tuple(x.digest() for x in bytype["observer_identity"])
    b=MoonSurfaceEvidenceBundle(sd,bytype["effect_contract"][0].digest(),bytype["authority_source"][0].digest(),bytype["currentness_source"][0].digest(),bytype["pep_identity"][0].digest(),bytype["execution_boundary"][0].digest(),obs,bytype["reconciliation_boundary"][0].digest(),bytype["replay_guard"][0].digest(),bytype["bounded_scope"][0].digest(),bytype["verifier_identity"][0].digest(),(),tuple(dict.fromkeys(base.evidence_refs+record.evidence_refs+(f"observation-rule:{rule.digest()}",)))).validate()
    return tuple(new),b,rule

def adjudicated_bindings_and_chains(*,inventory:EffectSurfaceInventory,records:Mapping[str,RunnerAttestedAdjudicationRecord]):
    base=materialize_seven(inventory=inventory);known={s.digest():s for s in inventory.surfaces};traces={t.surface_digest:t for t in ProductionEffectInventory().materialize(inventory=inventory,runtime_evidence=certified_runtime_evidence())};epoch=EPOCH_PREFIX+inventory.revision[:12]
    resolver=SurfaceBindingResolver();registry=MediationBindingRegistry(inventory_digest=inventory.digest(),epoch=epoch);reconstructor=MediationChainReconstructor();bindings={};chains={};bundles={};components={};promotions=[]
    for sd in sorted(set(FENCE_SURFACES)|{PERMISSION_SURFACE}):
        surface=known[sd]
        if sd==CREATE_TABLE_SURFACE: comps,bundle,rule=_adjudicated_bundle(inventory=inventory,surface=surface,base_artifacts=base,record=records["OBSERVE_SCHEMA"]);promotions.extend((next(c.digest() for c in comps if c.component_type=="observer_identity" and dict(c.payload).get("role")=="effect-readback"),rule.digest()))
        elif sd==PRAGMA_SURFACE: comps,bundle,rule=_adjudicated_bundle(inventory=inventory,surface=surface,base_artifacts=base,record=records["OBSERVE_SAME_CONNECTION_PRAGMA"]);promotions.extend((next(c.digest() for c in comps if c.component_type=="observer_identity" and dict(c.payload).get("role")=="effect-readback"),rule.digest()))
        else: comps=base.components[sd];bundle=base.bundles[sd]
        components[sd]=comps;bundles[sd]=bundle
        candidate=MediationBindingCandidate(inventory.digest(),sd,bundle.effect_contract_digest,bundle.pep_identity_digest,bundle.authority_source_digest,bundle.currentness_source_digest,bundle.execution_boundary_digest,bundle.replay_guard_digest,bundle.observer_identity_digests,bundle.reconciliation_boundary_digest,surface.effect_provider,surface.entrypoints[0],bundle.evidence_refs,epoch).validate()
        binding=resolver.resolve(inventory=inventory,surface=surface,candidate=candidate);registry.register(candidate,binding);bindings[sd]=binding
        trace=traces[sd]
        if trace.epistemic_state!="OBSERVED":raise AttestedAdjudicationError("expected observed trace")
        chain=reconstructor.reconstruct(inventory=inventory,trace=trace,binding=binding,replay_guard_digest=bundle.replay_guard_digest,bounded_scope_digest=bundle.bounded_scope_digest,verifier_identity_digest=bundle.verifier_identity_digest,epoch=epoch)
        if chain is None:raise AttestedAdjudicationError("chain incomplete")
        chains[sd]=chain
    return base,bundles,components,bindings,chains,tuple(promotions)

def convert_bypass_results(*,inventory:EffectSurfaceInventory,records:Mapping[str,RunnerAttestedAdjudicationRecord],definitions:Tuple[CanonicalAttackDefinition,...],policy:MediationAttackRequirementPolicy,rebind:RevisionRebindProof,bindings:Mapping[str,object])->Tuple[Tuple[BypassFalsificationResult,...],Mapping[str,str]]:
    defs={d.attack_id:d for d in definitions};requirements={r.surface_digest:r for r in policy.requirements};out=[];decisions={}
    mapping={"DENY_REPLAYED_EFFECT_KEY":("REPLAYED_EFFECT_KEY",PREPARED_SURFACE),"DENY_REPOSITORY_SUBSTITUTION":("REPOSITORY_SUBSTITUTION",PERMISSION_SURFACE),"DENY_ACTOR_SUBSTITUTION":("ACTOR_SUBSTITUTION",PERMISSION_SURFACE),"DENY_CONTROL_ISSUE_SUBSTITUTION":("CONTROL_ISSUE_SUBSTITUTION",PERMISSION_SURFACE)}
    decisions["DENY_WRONG_EXPECTED_STATE"]="EVIDENCE_ONLY:FAMILY_SCOPE_WITHOUT_EXPLICIT_SHARED_CLOSURE_COVERAGE"
    for op,(aid,sd) in mapping.items():
        rec=records[op];definition=defs[aid];req=requirements[sd]
        if aid not in req.attack_ids:raise AttestedAdjudicationError("converted attack absent from policy")
        idx=req.attack_ids.index(aid)
        if req.expected_pep_digests[idx]!=definition.expected_pep_digest:raise AttestedAdjudicationError("policy PEP mismatch")
        if aid=="REPLAYED_EFFECT_KEY" and definition.expected_pep_digest!=bindings[PREPARED_SURFACE].pep_identity_digest:raise AttestedAdjudicationError("replay PEP does not match PREPARED binding")
        if aid=="ACTOR_SUBSTITUTION" and definition.expected_pep_digest!=bindings[PERMISSION_SURFACE].pep_identity_digest:raise AttestedAdjudicationError("actor PEP does not match permission binding")
        if rec.result!="DENIED":raise AttestedAdjudicationError("non-denied receipt cannot convert")
        verifier=AttestedVerifierIdentity(rec.adjudication_digest,rec.run_id_numeric,rec.job_id_numeric,rec.runner_name,rec.runner_agent_id,rec.source_bridge_blob_sha,"runner-attested GitHub run/job adjudicator").validate()
        refs=(f"adjudication:{rec.adjudication_digest}",f"outer-receipt:{rec.outer_receipt_digest}",f"inner-result:{rec.inner_result_digest}",f"github-actions-run:{rec.run_id_numeric}",f"github-actions-job:{rec.job_id_numeric}",f"rebind:{rebind.digest()}",f"attack-definition:{definition.digest()}",f"attack-policy:{policy.digest()}")
        r=BypassFalsificationResult(aid,inventory.digest(),sd,definition.pep_name,definition.expected_pep_digest,"DENIED",refs,verifier.digest(),"OBSERVED",EPOCH_PREFIX+inventory.revision[:12]).validate();out.append(r);decisions[op]="CONVERTED:"+sd+":"+r.digest()
    return tuple(out),decisions

@dataclass(frozen=True)
class AdjudicationArtifacts:
    records:Mapping[str,RunnerAttestedAdjudicationRecord];definitions:Tuple[CanonicalAttackDefinition,...];policy:MediationAttackRequirementPolicy;rebind:RevisionRebindProof
    bindings:Mapping[str,object];chains:Mapping[str,object];bypass_results:Tuple[BypassFalsificationResult,...];conversion_decisions:Mapping[str,str];plan:AttestedAdjudicationPlan

def materialize_attested_adjudication(*,inventory:EffectSurfaceInventory,repo_root:Path)->AdjudicationArtifacts:
    inventory.validate()
    if inventory.scan_digest!=EXPECTED_SCAN_DIGEST:raise AttestedAdjudicationError("production scan digest drift")
    records=adjudicate_live_receipts();base,bundles,components,bindings,chains,promotions=adjudicated_bindings_and_chains(inventory=inventory,records=records)
    definitions=canonical_attack_definitions(inventory=inventory,base_artifacts=base);policy=attack_policy(inventory=inventory,definitions=definitions);rebind=revision_rebind_proof(inventory=inventory,repo_root=repo_root)
    results,decisions=convert_bypass_results(inventory=inventory,records=records,definitions=definitions,policy=policy,rebind=rebind,bindings=bindings)
    evidence_only=tuple(sorted(op for op in records if op.startswith("DENY_") and op not in decisions or decisions.get(op,"").startswith("EVIDENCE_ONLY")))
    plan=AttestedAdjudicationPlan(inventory.digest(),tuple(sorted(r.adjudication_digest for r in records.values())),policy.digest(),rebind.digest(),tuple(sorted(promotions)),len(bindings),len(chains),tuple(sorted(r.digest() for r in results)),evidence_only,"UNKNOWN",("seven-live-receipts:adjudicated","no-inner-payload-fabrication","no-mediated-promotion")).validate()
    return AdjudicationArtifacts(records,definitions,policy,rebind,bindings,chains,results,decisions,plan)
