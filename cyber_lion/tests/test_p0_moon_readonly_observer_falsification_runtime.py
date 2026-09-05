from __future__ import annotations
from pathlib import Path
import ast,inspect,sqlite3,subprocess,tempfile,unittest
from unittest.mock import patch

from cyber_lion.contracts.moon_file_write import MoonFileWriteContractError,MoonFileWriteRequest
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.moon_file_write_mediation import CanonicalMoonFileWriteMediator,DurableMoonFileWriteFence
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_readonly_observer_falsification import (
    ATTACK_IDS,EXPECTED_COLUMNS,MoonBoundedFalsificationRuntimeCandidate,
    MoonFenceReadOnlyObserverCandidate,MoonObserverRuntimeError,materialize_observer_runtime,
)

REPO="DonkeyJJLove/ai_platform"
EXPECTED_SCAN="8ee66a2523a0b03784ecd283a7c502d928abd0a342b087b236f1c9c6de01c71c"
CREATE_BLOCKED="478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d"
PRAGMA_BLOCKED="e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0"
SCHEMA="CREATE TABLE moon_file_write_effect(effect_key TEXT PRIMARY KEY,admission_digest TEXT UNIQUE NOT NULL,request_digest TEXT UNIQUE NOT NULL,repository TEXT NOT NULL,target_path TEXT NOT NULL,state TEXT NOT NULL,prepared_at TEXT NOT NULL,attempted_at TEXT,observed_at TEXT,reconciled_at TEXT,pre_observation_digest TEXT,post_observation_digest TEXT,reconciliation_digest TEXT)"

def current_inventory():
    root=Path(__file__).resolve().parents[2];sources={}
    for base in (root/"cyber_lion",root/".github/workflows"):
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in {".py",".yml",".yaml"}:sources[p.relative_to(root).as_posix()]=p.read_text(encoding="utf-8")
    revision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip();tree=subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=root,text=True).strip()
    raw=EffectSurfaceScanner().scan(repository=REPO,revision=revision,tree_digest=tree,sources=sources)
    inventory,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=sources);return inventory,report

def make_db(path:Path,*,wal=True,schema=SCHEMA):
    c=sqlite3.connect(path)
    if wal:c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=FULL")
    c.execute(schema);c.commit();c.close()

def request(**changes):
    values=dict(schema_version="1.0.0",request_id="candidate",repository="DonkeyJJLove/ai_platform",control_issue=144,actor_login="DonkeyJJLove",runner_name="lion-moon-r9d8-test",target_path="/home/d2j3/lion-p0-moon-replace-live-cert-r1.canary",operation_mode="REPLACE_EXPECTED_DIGEST",expected_previous_state="PRESENT_EXACT",expected_previous_sha256="a"*64,intended_content_sha256="b"*64,intended_content_size=1,source_event_digest="c"*64)
    values.update(changes);return MoonFileWriteRequest(**values)

class MoonReadonlyObserverFalsificationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.inventory,cls.taxonomy=current_inventory();cls.artifacts=materialize_observer_runtime(inventory=cls.inventory)

    def _observer_for(self,path:Path):
        import tools.p0_moon_readonly_observer_falsification as mod
        return patch.object(mod,"FENCE_PATH",str(path))

    def test_revision_bound_candidate_exact_and_no_live_evidence(self):
        self.assertEqual(self.inventory.scan_digest,EXPECTED_SCAN)
        p=self.artifacts.plan
        self.assertEqual(set(p.blocked_surface_digests),{CREATE_BLOCKED,PRAGMA_BLOCKED})
        self.assertEqual(len(self.artifacts.attack_plans),5)
        self.assertEqual(p.observer_receipt_count,0);self.assertEqual(p.bypass_result_count,0)
        self.assertFalse(p.live_observation_executed);self.assertFalse(p.live_falsification_executed);self.assertEqual(p.global_status,"UNKNOWN")
        self.assertTrue(self.artifacts.observer_spec.same_connection_synchronous_probe_required)

    def test_observer_mode_ro_query_only_schema_and_pragma_exact(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"fence.sqlite3";make_db(p)
            with self._observer_for(p):
                observer=MoonFenceReadOnlyObserverCandidate();readback=observer.inspect()
                self.assertTrue(readback.query_only);self.assertEqual(readback.columns,EXPECTED_COLUMNS);self.assertTrue(readback.schema_exact);self.assertTrue(readback.journal_mode_exact);self.assertTrue(readback.synchronous_value_exact);self.assertFalse(readback.synchronous_historical_proof)
                c=observer._connect_readonly()
                try:
                    with self.assertRaises(sqlite3.OperationalError):c.execute("CREATE TABLE forbidden_write(x INTEGER)")
                finally:c.close()

    def test_wrong_schema_and_wrong_pragma_denied(self):
        with tempfile.TemporaryDirectory() as td:
            wrong_schema=Path(td)/"wrong_schema.sqlite3";make_db(wrong_schema,schema="CREATE TABLE moon_file_write_effect(effect_key TEXT PRIMARY KEY)")
            with self._observer_for(wrong_schema),self.assertRaises(MoonObserverRuntimeError):MoonFenceReadOnlyObserverCandidate().inspect()
            wrong_pragma=Path(td)/"wrong_pragma.sqlite3";make_db(wrong_pragma,wal=False)
            with self._observer_for(wrong_pragma),self.assertRaises(MoonObserverRuntimeError):MoonFenceReadOnlyObserverCandidate().inspect()

    def test_request_level_future_denials_are_real_contract_denials(self):
        cases=(
            ({"expected_previous_state":"ABSENT","expected_previous_sha256":None},"REPLACE_EXPECTED_DIGEST requires exact pre-state"),
            ({"repository":"Other/repository"},"fixed execution context mismatch"),
            ({"actor_login":""},"actor_login invalid"),
            ({"control_issue":145},"fixed execution context mismatch"),
        )
        for changes,message in cases:
            with self.subTest(changes=changes),self.assertRaisesRegex(MoonFileWriteContractError,message):request(**changes).validate()

    def test_replay_denial_is_before_attempted_and_effect_boundary_in_source(self):
        prepare=inspect.getsource(DurableMoonFileWriteFence.prepare)
        execute=inspect.getsource(CanonicalMoonFileWriteMediator.execute)
        self.assertIn("durable file-write replay denied",prepare)
        self.assertLess(execute.index(".prepare("),execute.index(".mark_attempted("))
        self.assertLess(execute.index(".mark_attempted("),execute.index(".write_exact("))

    def test_exact_five_future_attack_plans_are_inert_and_bounded(self):
        runtime=MoonBoundedFalsificationRuntimeCandidate(self.inventory.revision)
        self.assertEqual(tuple(p.attack_id for p in self.artifacts.attack_plans),ATTACK_IDS)
        for p in self.artifacts.attack_plans:
            self.assertTrue(p.denial_before_effect_boundary);self.assertTrue(p.canary_unchanged_by_construction);self.assertFalse(p.valid_fence_state_transition_reached);self.assertFalse(p.live_execution);self.assertTrue(p.observation_receipt_required)
        spec=runtime.spec();self.assertFalse(spec.live_execution);self.assertFalse(spec.direct_database_write);self.assertFalse(spec.generic_shell);self.assertFalse(spec.subprocess_enabled)
        with self.assertRaises(MoonObserverRuntimeError):runtime.execute()

    def test_unknown_attack_arbitrary_path_and_command_denied(self):
        runtime=MoonBoundedFalsificationRuntimeCandidate(self.inventory.revision)
        with self.assertRaises(MoonObserverRuntimeError):runtime.plan("UNKNOWN")
        with self.assertRaises(MoonObserverRuntimeError):runtime.plan("WRONG_EXPECTED_STATE",target_path="/tmp/other")
        with self.assertRaises(MoonObserverRuntimeError):runtime.plan("WRONG_EXPECTED_STATE",command="not-allowed")

    def test_candidate_source_has_no_generic_execution_primitives(self):
        root=Path(__file__).resolve().parents[2];source=(root/"tools/p0_moon_readonly_observer_falsification.py").read_text(encoding="utf-8");tree=ast.parse(source)
        imports=[];calls=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
            elif isinstance(n,ast.ImportFrom):imports.append(n.module or "")
            elif isinstance(n,ast.Call):
                if isinstance(n.func,ast.Name):calls.append(n.func.id)
                elif isinstance(n.func,ast.Attribute):calls.append(n.func.attr)
        self.assertNotIn("subprocess",imports);self.assertNotIn("importlib",imports)
        self.assertFalse({"eval","exec","__import__","system","Popen","run"}&set(calls))

    def test_observer_receipt_api_has_no_external_readback_parameter(self):
        sig=inspect.signature(MoonFenceReadOnlyObserverCandidate.observe_live)
        self.assertNotIn("readback",sig.parameters)
        self.assertIn("revision",sig.parameters);self.assertIn("tree",sig.parameters);self.assertIn("observed_at",sig.parameters)

if __name__=="__main__":unittest.main()
