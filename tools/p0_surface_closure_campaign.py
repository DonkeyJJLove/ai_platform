"""Build the exact evidence-only 235-surface closure campaign from current inventory."""
from __future__ import annotations
from collections import defaultdict
from typing import Mapping,Tuple
from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from tools.p0_surface_closure_campaign_contract import ProviderFamilyClosurePlan,SurfaceClosureCampaign,SurfaceClosureWorkItem

EXPECTED_SCAN_DIGEST="cf13b4c46d1c77a58a2d9ee4d839a4994aa18ff126713886bc5e62649b998c18"
CERTIFIED_PARTIAL_SURFACE="8c6d0020a0816d674a783504d2a8ccc25e3e75c0d446057ba3f4450bd768f687"
MOON_PROVIDERS=frozenset({
    ".github.workflows.moon-file-write.yml",
    "cyber_lion.enterprise.moon_file_write.py",
    "cyber_lion.enterprise.moon_file_write_mediation.py",
})
RECEIPT_IMPLIED_MOON_SURFACES=frozenset({
    "e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0",
    "478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d",
    "e5e829051f5e73e2d4f8135c1b6e1bc76e4712b6e4a91162ddd6cd218eac406b",
    "135df096a721d0932a9ee3b51f93bb19a130f2bd68e96535e646d5e78311fd0c",
    "39ad42d545df0e5fd80b99266dc419a84dc1528746e398ecbdeb69b63f631484",
    "99cfcdb99882099f89c90f9247e1bf13eaacb48422c7e276bed43e216e419fad",
    "dbff98ee0801784d8616fc32d67dfbb2ea19fbfcc1cfbda829cf904953f5631b",
})
LIVE_RECEIPT_REFS=(
    "github-actions-run:33911284689",
    "github-actions-job:101148041371",
    "moon-effect-key:3ad38b9be4ea737d77c672f97f430cb32a4ba432327f5d1086e38f18327dc4c8",
    "moon-reconciliation-digest:6648aeb323c104946ec91e5e2af4c53282f01561ed4dce2d7867775c0812819e",
)
SHARED_REQUIREMENTS=(
    "effect-contract",
    "authority-source",
    "currentness-source",
    "pep-identity",
    "execution-boundary",
    "observer-identities",
    "reconciliation-boundary",
    "replay-guard",
    "bounded-scope",
    "observed-bypass-results",
)

class SurfaceClosureCampaignError(RuntimeError):pass

class SurfaceClosureCampaignBuilder:
    def materialize(self,*,inventory:EffectSurfaceInventory,runtime_evidence:Mapping[str,Tuple[str,...]],excluded_surface_digests:Tuple[str,...]=(CERTIFIED_PARTIAL_SURFACE,),live_falsification_carrier_state:str="ABSENT",evidence_refs:Tuple[str,...]=())->SurfaceClosureCampaign:
        inventory.validate()
        if inventory.scan_digest!=EXPECTED_SCAN_DIGEST:raise SurfaceClosureCampaignError("production scan digest drift")
        known={s.digest():s for s in inventory.surfaces}
        excluded=set(excluded_surface_digests)
        if excluded-set(known):raise SurfaceClosureCampaignError("excluded surface outside inventory")
        if set(runtime_evidence)-set(known):raise SurfaceClosureCampaignError("runtime evidence outside inventory")
        if set(runtime_evidence)&excluded:raise SurfaceClosureCampaignError("excluded surface cannot re-enter campaign")
        counts=defaultdict(int)
        for sd,s in known.items():
            if sd not in excluded:counts[s.effect_provider]+=1
        items=[]
        for sd in sorted(set(known)-excluded):
            s=known[sd]
            refs=tuple(runtime_evidence.get(sd,()))
            runtime_state="OBSERVED" if refs else "UNKNOWN"
            priority=1 if s.effect_provider in MOON_PROVIDERS else (2 if counts[s.effect_provider]>1 else 3)
            required=("binding","chain","observed-bypass-results","live-falsification-carrier") if refs else ("runtime-trace","binding","chain","observed-bypass-results","live-falsification-carrier")
            items.append(SurfaceClosureWorkItem(sd,s.effect_provider,s.effect_class,s.authority_class,s.target_class,s.entrypoints[0],runtime_state,refs,"ABSENT","ABSENT","ABSENT","PARTIAL" if refs else "UNKNOWN",required,priority).validate())
        by_provider=defaultdict(list)
        for item in items:by_provider[item.provider].append(item)
        families=[]
        for provider,group in by_provider.items():
            priority=group[0].priority
            families.append(ProviderFamilyClosurePlan(
                provider,priority,tuple(sorted(x.surface_digest for x in group)),tuple(sorted(x.surface_digest for x in group if x.runtime_state=="OBSERVED")),
                tuple(sorted({x.effect_class for x in group})),tuple(sorted({x.authority_class for x in group})),tuple(sorted({x.target_class for x in group})),SHARED_REQUIREMENTS,
            ).validate())
        families.sort(key=lambda x:(x.priority,-len(x.surface_digests),x.provider))
        first=tuple(sorted(x.surface_digest for x in items if x.priority==1 and x.runtime_state=="OBSERVED"))
        if not first:raise SurfaceClosureCampaignError("no observed safe first batch")
        return SurfaceClosureCampaign(
            inventory.repository,inventory.revision,inventory.tree_digest,inventory.digest(),inventory.scan_digest,len(inventory.surfaces),len(items),tuple(sorted(excluded)),tuple(items),tuple(families),first,live_falsification_carrier_state,
            tuple(evidence_refs),"UNKNOWN",
        ).validate()

def certified_runtime_evidence()->dict[str,Tuple[str,...]]:
    return {sd:LIVE_RECEIPT_REFS for sd in sorted(RECEIPT_IMPLIED_MOON_SURFACES)}
