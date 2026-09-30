import json
from pathlib import Path
import tempfile
import unittest

from tools.lion_federated_architecture_knowledge import (
    build_census,
    build_dependency_graph,
    build_document_graph,
    build_reconciliation,
    project,
)


def manifest(repo,branch,*,dependency=()):
    return {
      "schema_version":"1.0.0",
      "repository":{"id":repo,"url":"https://example.invalid/"+repo,"owner":"DonkeyJJLove","default_branch":branch,"vcs_ref":None},
      "cyber_lion":{"tile_id":"tile."+repo.split("/")[-1],"roles":["Role"],"layers":["SEM"],"disposition":["KEEP"]},
      "capabilities":["x"],
      "authority":{"maximum_level":"read","required_gates":["g"]},
      "observability":{"logs":["l"],"metrics":["m"],"traces":["t"]},
      "security":{"trust_boundaries":["proposal != authority"]},
      "epistemic":{"status":"OBSERVED","confidence":0.8},
      "architecture_knowledge":{
        "schema_version":"1.0.0","global_owner":"DonkeyJJLove/ai_platform",
        "semantic_exports":["x."+repo.split("/")[-1]],"semantic_imports":["architecture"],
        "repository_dependencies":list(dependency),
        "architecture_artifacts":[{"path":"AGENTS.md","class":"HUMAN_ARCHITECTURE_DOCUMENT","currentness":"LOCAL_OWNER"}],
        "discoverability":{"entrypoint":"AGENTS.md","global_owner_route":"manifest -> ai_platform","max_reads_to_global_owner":3},
        "invalidation_triggers":["SOURCE_CHANGE","DEPENDENCY_CHANGE"],
      },
    }


def snapshot():
    names=[
      ("DonkeyJJLove/ai_platform","master"),("DonkeyJJLove/chunk-chunk","master"),("DonkeyJJLove/glitchlab","master"),
      ("DonkeyJJLove/HA2D","master"),("DonkeyJJLove/hipotezy_nadawcze_LLM","main"),("DonkeyJJLove/mosaic_lab_pro.py","main"),
      ("DonkeyJJLove/sbom","main"),("DonkeyJJLove/swarm","master"),("DonkeyJJLove/SymulacjaKaskadySieciowej","main"),("DonkeyJJLove/writeups","master")
    ]
    rows=[]
    for i,(repo,branch) in enumerate(names):
        deps=() if repo=="DonkeyJJLove/ai_platform" else ("DonkeyJJLove/ai_platform",)
        files=[{"path":"cyber-lion.repository.json","blob":f"{i:040x}"},{"path":"AGENTS.md","blob":f"{i+20:040x}"}]
        if repo=="DonkeyJJLove/ai_platform":
            files += [
              {"path":"LION/architecture/v1_4/federation_current_vector.json","blob":"a"*40},
              {"path":"LION/architecture/v1_5/README.md","blob":"b"*40},
            ]
        rows.append({"repository":repo,"branch":branch,"head":f"{i+1:040x}","tree":f"{i+101:040x}","manifest_blob":f"{i+201:040x}","manifest":manifest(repo,branch,dependency=deps),"files":files})
    return {"schema":"lion.federation-live-snapshot/v1","repositories":rows}


class FederatedArchitectureKnowledgeProjectionTests(unittest.TestCase):
    def test_projection_is_deterministic(self):
        s=snapshot()
        self.assertEqual(project(s),project(s))

    def test_all_ten_repositories_are_censused(self):
        c=build_census(snapshot())
        repos={x["repository"] for x in c["artifacts"]}
        self.assertEqual(len(repos),10)

    def test_dependency_graph_uses_manifest_dependencies(self):
        g=build_dependency_graph(snapshot())
        edges={(x["source"],x["target"],x["relation"]) for x in g["edges"]}
        self.assertIn(("DonkeyJJLove/swarm","DonkeyJJLove/ai_platform","DEPENDS_ON"),edges)

    def test_document_graph_routes_agents_to_manifest(self):
        s=snapshot();c=build_census(s);g=build_document_graph(s,c)
        self.assertTrue(any(x["relation"]=="ROUTED_BY" and "swarm:AGENTS.md" in x["source"] for x in g["edges"]))

    def test_missing_declared_entrypoint_is_detected(self):
        s=snapshot()
        swarm=next(x for x in s["repositories"] if x["repository"]=="DonkeyJJLove/swarm")
        swarm["files"]=[x for x in swarm["files"] if x["path"]!="AGENTS.md"]
        c=build_census(s);r=build_reconciliation(s,c)
        self.assertTrue(any(x["classification"]=="DISCOVERABILITY_MISSING" for x in r["contradictions"]))


if __name__=="__main__":
    unittest.main()
