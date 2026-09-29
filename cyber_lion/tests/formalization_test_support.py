from cyber_lion.contracts.formalization_registry import FormalizationArtifact, FormalizationRegistry
from cyber_lion.contracts.architecture_formalization_manifest import *
from cyber_lion.architecture_projection.formalization import derive_required_formalization_set
from cyber_lion.contracts.formalization_closure import *

def registry():
    import json
    from pathlib import Path
    p=Path(__file__).resolve().parents[2]/"LION/architecture/v1_5/FORMALIZATION_REGISTRY_CANDIDATE.json"
    return FormalizationRegistry.from_dict(json.loads(p.read_text(encoding="utf-8")))

def base(): return BaselineIdentity("DonkeyJJLove/ai_platform","master","1"*40,"2"*40)
def global_updates():
    return (
      FormalizationUpdate("semantic-owners","UPDATE","owners changed"), FormalizationUpdate("contract-catalog","UPDATE","contracts changed"),
      FormalizationUpdate("capability-catalog","VALIDATE_ONLY","capability impact inspected"), FormalizationUpdate("architecture-projection","UPDATE","architecture changed"),
      FormalizationUpdate("event-state-catalog","VALIDATE_ONLY","event semantics inspected"), FormalizationUpdate("gap-projection","UPDATE","frontier changed"),
      FormalizationUpdate("evolution-evals","UPDATE","behavioral evals changed"), FormalizationUpdate("discoverability-bootstrap","UPDATE","routing changed"),
      FormalizationUpdate("rag-routing","UPDATE","rag routing changed"), FormalizationUpdate("currentness-carriers","REGENERATE","truth currentness invalidated"),
    )
def manifest(reg=None, **kw):
    reg=reg or registry(); updates=kw.pop("formalization_updates",global_updates()); invalid=tuple(x.artifact_id for x in updates if x.operation in {"UPDATE","REGENERATE","ADD","SUPERSEDE"})
    x=ArchitectureFormalizationManifest(
      manifest_id="afm:test",baseline=base(),source_evolution_delta=EvolutionDeltaRef("delta:test","3"*64),change_class=kw.pop("change_class","ARCHITECTURE_CONCEPT"),affected_concepts=("test_concept",),
      layer_bindings=(LayerBinding("test_concept",("EVOLUTIONARY_EPOCH","ARCHITECTURE_PROJECTION"),False),), semantic_owner_delta=(SemanticOwnerDelta("test_concept","cyber_lion/contracts/test.py",(),"ADD"),),
      formalization_updates=updates,currentness_invalidations=kw.pop("currentness_invalidations",invalid),migration=MigrationPlan(("add",),None,"done"),rollback=MigrationPlan(("remove",),None,"restored"),
      tests_required=("t1",),evals_required=("e1",),falsifiers=("f1",),discoverability=DiscoverabilityPlan(("AGENTS -> registry",),("owner?",),3),rag_delta=RagDelta(True,("R1",),("probe",)),**kw)
    return x.sealed(reg)
