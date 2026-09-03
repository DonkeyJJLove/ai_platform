from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import lcms  # candidate-only compiler tool, deliberately outside runtime package
from cyber_lion.tests.test_action_spec_schema import _validate

SCHEMA = json.loads((ROOT / "cyber_lion/contracts/v1/action_spec.schema.json").read_text())
MATRIX = json.loads((ROOT / "cyber_lion/contracts/v1/action_spec_support_matrix.json").read_text())
PROPOSAL = json.loads((ROOT / "cyber_lion/contracts/v1/action_proposal.schema.json").read_text())
SHA = "9082a974e8105dd7e47afc889583b1fc67535b59"
TREE = "1414a21efce8f35892134060cd0d77f2d4d08e9b"

BASE = [
    lcms.LCMS_HEADER,
    'schema_version="lion.action-spec/v1.3-candidate"',
    'action_id="c1.observe.1"',
    'kind="repository.observe"',
    'intent_ref="intent:c1"',
    'mission_ref="mission:c1"',
    'autonomy_ref="autonomy:lion"',
    'bean_ref="bean:c1"',
    'target.host="github"',
    'target.environment="candidate"',
    'target.runtime="schema-only"',
    'authority_request.domain="repository"',
    'authority_request.capability="observe"',
    'authority_request.grant_ref=null',
    'boundary.shell=false',
    'boundary.network="DENY"',
    'boundary.filesystem_read=[]',
    'boundary.filesystem_write=[]',
    'boundary.process_children=[]',
    'boundary.timeout_ms=1000',
    'boundary.max_processes=1',
    'boundary.memory_limit_bytes=1048576',
    'preconditions=["baseline-exact"]',
    'expected_effects=[]',
    'forbidden_effects=["runtime-execution","authority-effect","transport-effect"]',
    'observation.observer_class="deterministic_independent"',
    'observation.required_events=["schema-validated"]',
    'reconciliation.mode="EXACT"',
    'reconciliation.receipt="REQUIRED"',
]

def src(l=None): return "\n".join(l or BASE) + "\n"
def replace(lines, prefix, value):
    r=list(lines)
    for i,x in enumerate(r):
        if x.startswith(prefix):
            if value is None: r.pop(i)
            else: r[i]=value
            return r
    raise AssertionError(prefix)

def process():
    r=replace(BASE, "kind=", 'kind="process.exec"')
    r+=[
        'executable.path="/usr/bin/python3"',
        'executable.digest="sha256:' + "0"*64 + '"',
        'arguments=["-V"]',
        'workspace.repository="DonkeyJJLove/ai_platform"',
        f'workspace.commit="{SHA}"', f'workspace.tree="{TREE}"',
        'workspace.path="/workspace"', 'environment.inherit=false',
        'environment.allow={}', 'io.stdin="NONE"', 'io.stdout="CAPTURE"',
        'io.stderr="CAPTURE"', 'io.tty=false',
    ]
    return r

class TestLLIONLCMS(unittest.TestCase):
    def code(self,source,expected):
        with self.assertRaises(lcms.LCMSError) as e: lcms.compile_lcms(source)
        self.assertEqual(e.exception.code, expected)

    def test_positive_and_schema_validation(self):
        for lines,kind in [(BASE,"repository.observe"),(process(),"process.exec")]:
            with self.subTest(kind=kind):
                c=lcms.compile_lcms(src(lines)); s=c.as_dict()
                self.assertEqual(s["kind"],kind); _validate(s,SCHEMA,SCHEMA)
        self.assertFalse(lcms.compile_lcms(src(process())).as_dict()["environment"]["inherit"])

    def test_fail_closed_matrix(self):
        cases=[
            (replace(BASE, "boundary.shell=", "boundary.shell=true"),"SHELL_TRUE"),
            (BASE+['command="echo a | cat"'],"RAW_SHELL_STRING"),
            (BASE+['kind="repository.observe"'],"DUPLICATE_FIELD"),
            (replace(BASE, "preconditions=", 'preconditions=["x","x"]'),"DUPLICATE_SET_MEMBER"),
            (BASE+['transport="forbidden"'],"UNKNOWN_FIELD"),
            (replace(BASE, "boundary.network=", 'boundary.network="MAYBE"'),"UNKNOWN_ENUM"),
            (replace(BASE, "kind=", 'kind="process.magic"'),"UNKNOWN_ACTION_KIND"),
            (replace(process(), "workspace.commit=", 'workspace.commit="abc"'),"MALFORMED_DIGEST"),
            (replace(process(), "executable.digest=", 'executable.digest="sha256:bad"'),"MALFORMED_DIGEST"),
            (replace(process(), "workspace.path=", 'workspace.path="/workspace/../escape"'),"PATH_TRAVERSAL"),
            (replace(process(), "executable.path=", 'executable.path="usr/bin/python3"'),"RELATIVE_EXECUTABLE_PATH"),
            (replace(process(), "environment.inherit=", "environment.inherit=true"),"ENVIRONMENT_INHERITANCE"),
            (replace(BASE, "boundary.network=",None),"IMPLICIT_DEFAULT_WITH_EFFECT"),
            (BASE+['cmd="python3 -V"'],"ALIAS_NOT_CANONICAL"),
            (replace(BASE, "boundary.timeout_ms=", 'boundary.timeout_ms="1000ms"'),"AMBIGUOUS_UNIT"),
            (replace(BASE, "boundary.shell=", "boundary.shell=0"),"AMBIGUOUS_BOOLEAN"),
            (replace(process(), "workspace.path=",None),"UNBOUND_WORKSPACE"),
            (replace(BASE, "forbidden_effects=", 'forbidden_effects=["x","x"]'),"DUPLICATE_SET_MEMBER"),
            (BASE+['pipeline.edge=["a","b"]'],"UNKNOWN_PIPELINE_EDGE"),
            (BASE+['pipeline.cycle=true'],"CYCLIC_PIPELINE"),
            (BASE+['pipeline.node="a"'],"UNDECLARED_PIPELINE_NODE"),
        ]
        for lines,code in cases:
            with self.subTest(code=code): self.code(src(lines),code)
        self.code(src().replace("c1.observe.1","c1.–observe.1"),"NONCANONICAL_UNICODE")

    def test_canonicalization_determinism(self):
        a=lcms.compile_lcms(src()); b=lcms.compile_lcms(src([BASE[0]]+list(reversed(BASE[1:]))))
        self.assertEqual(a.canonical_bytes,b.canonical_bytes); self.assertEqual(a.digest,b.digest)
        w=replace(BASE,"preconditions=", 'preconditions=[ "baseline-exact" ]')
        self.assertEqual(a.canonical_bytes,lcms.compile_lcms(src(w)).canonical_bytes)
        c=lcms.compile_lcms(src(process())); d=lcms.compile_lcms(src(process()))
        self.assertEqual(c.canonical_bytes,d.canonical_bytes); self.assertTrue(c.canonical_bytes.endswith(b"\n"))

    def test_compiler_is_non_effectful(self):
        t=Path(lcms.__file__).read_text().lower()
        for x in ("subprocess","os.system","urllib","http.client","socket","requests","effect_provider","transport_provider","credential_env","private_key","signing_key","merge_pull_request"): self.assertNotIn(x,t)
        tree = ast.parse(Path(lcms.__file__).read_text())
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        for name in ("open", "unlink", "replace", "write_text", "write_bytes", "system", "run", "Popen", "urlopen", "request"):
            self.assertNotIn(name, calls)

    def test_c0_contradictions_and_support_preserved(self):
        r={x["id"]:x for x in MATRIX["contradictions"]}
        self.assertEqual(r["C0-FINANCIAL-AUTHORITY-VOCABULARY"]["resolution"],"NO_SILENT_MAPPING")
        self.assertEqual(r["C0-V1_2-ACTIONSPEC-ABSENT"]["resolution"],"NEW_CANDIDATE_NOT_SUPERSESSION")
        self.assertEqual(r["C0-TARGET-SHAPE"]["resolution"],"NO_IMPLICIT_RUNTIME_COERCION")
        self.assertEqual(PROPOSAL["properties"]["target"]["type"],"string"); self.assertEqual(SCHEMA["properties"]["target"]["type"],"object")
        self.assertEqual(MATRIX["target_only"]["runtime_support"],"NONE_FROM_ACTIONSPEC_SCHEMA")
        self.assertEqual(MATRIX["target_only"]["transport_support"],"NONE"); self.assertEqual(MATRIX["target_only"]["authority_effect"],"NONE")

if __name__=="__main__": unittest.main()
