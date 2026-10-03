import json
from pathlib import Path
import unittest

from cyber_lion.enterprise.federation import RepositoryManifest, EnterpriseModelError

try:
    import jsonschema
except ImportError:
    jsonschema=None

ROOT=Path(__file__).resolve().parents[2]
SCHEMA=json.loads((ROOT/"cyber_lion/contracts/v1/repository_manifest.schema.json").read_text(encoding="utf-8"))


class RepositoryManifestArchitectureKnowledgeTests(unittest.TestCase):
    def setUp(self):
        if jsonschema is None:
            self.skipTest("jsonschema unavailable")
        self.base={
          "schema_version":"1.0.0",
          "repository":{"id":"DonkeyJJLove/swarm","url":"https://github.com/DonkeyJJLove/swarm","owner":"DonkeyJJLove","default_branch":"master","vcs_ref":None},
          "cyber_lion":{"tile_id":"execution-mesh.swarm","roles":["ExecutionMesh"],"layers":["INF"],"disposition":["KEEP"]},
          "capabilities":["workload.execute"],
          "authority":{"maximum_level":"external_write","required_gates":["cyber-lion.mand"]},
          "observability":{"logs":["runtime"],"metrics":["runtime"],"traces":["request→receipt"]},
          "security":{"trust_boundaries":["workload != authority"]},
          "epistemic":{"status":"ENGINEERING_CANDIDATE","confidence":0.8},
        }

    def architecture_knowledge(self):
        return {
          "schema_version":"1.0.0",
          "global_owner":"DonkeyJJLove/ai_platform",
          "semantic_exports":["runtime"],
          "semantic_imports":["authority"],
          "repository_dependencies":["DonkeyJJLove/ai_platform"],
          "architecture_artifacts":[{"path":"runtime/README.md","class":"HUMAN_ARCHITECTURE_DOCUMENT","currentness":"LOCAL_OWNER"}],
          "discoverability":{"entrypoint":"AGENTS.md","global_owner_route":"cyber-lion.repository.json -> DonkeyJJLove/ai_platform","max_reads_to_global_owner":3},
          "invalidation_triggers":["SOURCE_CHANGE","CONTRACT_CHANGE","DEPENDENCY_CHANGE"],
        }

    def test_legacy_manifest_remains_valid(self):
        jsonschema.Draft202012Validator(SCHEMA).validate(self.base)

    def test_architecture_knowledge_extension_is_valid(self):
        self.base["architecture_knowledge"]=self.architecture_knowledge()
        jsonschema.Draft202012Validator(SCHEMA).validate(self.base)

    def test_actual_repository_manifest_is_valid(self):
        value=json.loads((ROOT/'cyber-lion.repository.json').read_text(encoding='utf-8'))
        jsonschema.Draft202012Validator(SCHEMA).validate(value)

    def test_standardization_invalidation_triggers_are_valid(self):
        self.base['architecture_knowledge']=self.architecture_knowledge()
        self.base['architecture_knowledge']['invalidation_triggers'].extend([
            'NAMING_STANDARD_CHANGE','STATUS_MODEL_CHANGE','VERSION_MODEL_CHANGE',
            'PANEL_CONTRACT_CHANGE','REPOSITORY_CONTENT_CHANGE'])
        jsonschema.Draft202012Validator(SCHEMA).validate(self.base)

    def test_unknown_global_owner_is_denied(self):
        self.base["architecture_knowledge"]=self.architecture_knowledge()
        self.base["architecture_knowledge"]["global_owner"]="Other/repo"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(SCHEMA).validate(self.base)

    def test_discoverability_bound_is_enforced(self):
        self.base["architecture_knowledge"]=self.architecture_knowledge()
        self.base["architecture_knowledge"]["discoverability"]["max_reads_to_global_owner"]=99
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(SCHEMA).validate(self.base)


    def test_typed_parser_accepts_architecture_knowledge_extension(self):
        self.base["architecture_knowledge"]=self.architecture_knowledge()
        parsed=RepositoryManifest.from_mapping(self.base)
        self.assertIsNotNone(parsed.architecture_knowledge)
        self.assertEqual(parsed.architecture_knowledge.global_owner,"DonkeyJJLove/ai_platform")
        self.assertEqual(parsed.architecture_knowledge.semantic_exports,("runtime",))

    def test_typed_parser_keeps_legacy_manifest_compatible(self):
        parsed=RepositoryManifest.from_mapping(self.base)
        self.assertIsNone(parsed.architecture_knowledge)

    def test_typed_parser_rejects_unknown_architecture_knowledge_field(self):
        self.base["architecture_knowledge"]=self.architecture_knowledge()
        self.base["architecture_knowledge"]["unexpected"]="x"
        with self.assertRaisesRegex(EnterpriseModelError,"architecture_knowledge shape invalid"):
            RepositoryManifest.from_mapping(self.base)

    def test_typed_parser_rejects_duplicate_semantic_export(self):
        self.base["architecture_knowledge"]=self.architecture_knowledge()
        self.base["architecture_knowledge"]["semantic_exports"]=["runtime","runtime"]
        with self.assertRaisesRegex(EnterpriseModelError,"unique"):
            RepositoryManifest.from_mapping(self.base)


if __name__=="__main__":
    unittest.main()
