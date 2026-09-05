from __future__ import annotations
from dataclasses import dataclass, replace
from hashlib import sha1, sha256
from pathlib import Path
from typing import Tuple

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from cyber_lion.contracts.mediation_falsification import BypassFalsificationResult, MediationBindingCandidate
from cyber_lion.enterprise.mediation_falsification import MediationBindingRegistry, MediationFalsificationError, SurfaceBindingResolver
from tools.p0_moon_attack_registry import FENCE_SURFACES
from tools.p0_moon_attested_adjudication import AdjudicationArtifacts, SOURCE_BLOBS, materialize_attested_adjudication
from tools.p0_moon_structural_falsification_contract import StructuralFalsificationObservation, StructuralFalsificationPlan, StructuralFalsificationVerifierIdentity

STRUCTURAL_ATTACKS=("SURFACE_SUBSTITUTION","PROVIDER_SUBSTITUTION","ENTRYPOINT_SUBSTITUTION","CROSS_EPOCH_BINDING")
PRODUCTION_PEP_SOURCE="cyber_lion/enterprise/mediation_falsification.py"
ADAPTER_SOURCE="tools/p0_moon_structural_falsification.py"

class MoonStructuralFalsificationError(RuntimeError): pass

def _git_blob_sha(data:bytes)->str:
    return sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def _source_sha256(root:Path,path:str)->str:
    return sha256((root/path).read_bytes()).hexdigest()

def _production_blob(root:Path)->str:
    blob=_git_blob_sha((root/PRODUCTION_PEP_SOURCE).read_bytes())
    expected=SOURCE_BLOBS[PRODUCTION_PEP_SOURCE]
    if blob!=expected: raise MoonStructuralFalsificationError("production PEP source blob drift")
    return blob

def _candidate(*,inventory:EffectSurfaceInventory,surface,binding,chain)->MediationBindingCandidate:
    return MediationBindingCandidate(
        inventory.digest(),surface.digest(),binding.effect_contract_digest,binding.pep_identity_digest,binding.authority_source_digest,
        binding.currentness_source_digest,binding.execution_boundary_digest,chain.replay_guard_digest,binding.observer_identity_digests,
        binding.reconciliation_boundary_digest,surface.effect_provider,surface.entrypoints[0],tuple(ref for ref in binding.evidence_refs if not ref.startswith(("replay-guard:","candidate:"))),chain.epoch,
    ).validate()

def _expect_denial(call,expected:str)->str:
    try: call()
    except MediationFalsificationError as exc:
        actual=str(exc)
        if actual!=expected: raise MoonStructuralFalsificationError(f"unexpected structural denial: {actual!r} != {expected!r}") from exc
        return actual
    raise MoonStructuralFalsificationError("structural attack was not denied")

@dataclass(frozen=True)
class StructuralFalsificationArtifacts:
    verifier:StructuralFalsificationVerifierIdentity
    observations:Tuple[StructuralFalsificationObservation,...]
    bypass_results:Tuple[BypassFalsificationResult,...]
    plan:StructuralFalsificationPlan

def materialize_structural_falsification(*,inventory:EffectSurfaceInventory,repo_root:Path,adjudication:AdjudicationArtifacts|None=None)->StructuralFalsificationArtifacts:
    inventory.validate();repo_root=Path(repo_root)
    if adjudication is None: adjudication=materialize_attested_adjudication(inventory=inventory,repo_root=repo_root)
    if adjudication.policy.inventory_digest!=inventory.digest(): raise MoonStructuralFalsificationError("attack policy inventory drift")
    known={s.digest():s for s in inventory.surfaces}
    if set(FENCE_SURFACES)-set(known): raise MoonStructuralFalsificationError("fence surface drift")
    requirements={r.surface_digest:r for r in adjudication.policy.requirements}
    definitions={d.attack_id:d for d in adjudication.definitions}
    verifier=StructuralFalsificationVerifierIdentity(
        inventory.revision,inventory.tree_digest,_source_sha256(repo_root,ADAPTER_SOURCE),_production_blob(repo_root),
        "p0-moon-structural-production-resolver-verifier/1",
    ).validate()
    resolver=SurfaceBindingResolver(); observations=[]; results=[]
    for sd in sorted(FENCE_SURFACES):
        surface=known[sd];binding=adjudication.bindings[sd];chain=adjudication.chains[sd]
        base=_candidate(inventory=inventory,surface=surface,binding=binding,chain=chain)
        other=next(x for x in sorted(FENCE_SURFACES) if x!=sd)
        for aid in STRUCTURAL_ATTACKS:
            req=requirements[sd]
            if aid not in req.attack_ids: raise MoonStructuralFalsificationError("structural attack absent from policy")
            idx=req.attack_ids.index(aid);definition=definitions[aid]
            if req.expected_pep_digests[idx]!=definition.expected_pep_digest: raise MoonStructuralFalsificationError("structural PEP policy mismatch")
            candidate=base
            if aid=="SURFACE_SUBSTITUTION":
                candidate=replace(base,surface_digest=other).validate(); expected="surface substitution"
                denial=lambda candidate=candidate: resolver.resolve(inventory=inventory,surface=surface,candidate=candidate)
            elif aid=="PROVIDER_SUBSTITUTION":
                candidate=replace(base,provider_identity="substituted.invalid.provider").validate(); expected="provider substitution"
                denial=lambda candidate=candidate: resolver.resolve(inventory=inventory,surface=surface,candidate=candidate)
            elif aid=="ENTRYPOINT_SUBSTITUTION":
                candidate=replace(base,entrypoint_ref="substituted:0:entrypoint").validate(); expected="entrypoint substitution"
                denial=lambda candidate=candidate: resolver.resolve(inventory=inventory,surface=surface,candidate=candidate)
            elif aid=="CROSS_EPOCH_BINDING":
                expected="cross-epoch binding replay"
                structural_binding=resolver.resolve(inventory=inventory,surface=surface,candidate=base)
                denial=lambda candidate=base,structural_binding=structural_binding: MediationBindingRegistry(inventory_digest=inventory.digest(),epoch=base.epoch+":OTHER").register(candidate,structural_binding)
            else: raise MoonStructuralFalsificationError("unknown structural attack")
            observed=_expect_denial(denial,expected)
            refs=(f"production-pep-source:{PRODUCTION_PEP_SOURCE}@{verifier.production_pep_source_blob_sha}",f"candidate:{candidate.digest()}",f"attack-definition:{definition.digest()}",f"attack-policy:{adjudication.policy.digest()}",f"verifier:{verifier.digest()}")
            obs=StructuralFalsificationObservation(aid,inventory.digest(),sd,definition.expected_pep_digest,definition.pep_name,candidate.digest(),observed,verifier.digest(),inventory.revision,inventory.tree_digest,base.epoch,refs).validate()
            result_refs=refs+(f"structural-observation:{obs.digest()}",)
            result=BypassFalsificationResult(aid,inventory.digest(),sd,definition.pep_name,definition.expected_pep_digest,"DENIED",result_refs,verifier.digest(),"OBSERVED",base.epoch).validate()
            observations.append(obs);results.append(result)
    keys={(r.surface_digest,r.attack_id) for r in results}
    if len(results)!=24 or len(keys)!=24: raise MoonStructuralFalsificationError("structural result matrix not exact")
    plan=StructuralFalsificationPlan(inventory.digest(),adjudication.policy.digest(),verifier.digest(),tuple(sorted(x.digest() for x in observations)),tuple(sorted(x.digest() for x in results)),6,24,"UNKNOWN",("structural-only:no-live-execution","production-resolver-invoked-directly","unit-test-pass-not-used-as-result")).validate()
    return StructuralFalsificationArtifacts(verifier,tuple(observations),tuple(results),plan)
