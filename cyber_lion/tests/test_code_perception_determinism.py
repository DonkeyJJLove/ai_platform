import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cyber_lion.contracts.code_perception import SourceIdentity
from cyber_lion.enterprise.code_perception import (
    BlobInput,
    CodePerceptionBuildError,
    build_code_graph,
    build_from_git,
    git_blob_inputs,
    git_source_identity,
    tree_semantic_digest,
)

REPOSITORY = "DonkeyJJLove/ai_platform"

def fixture_blob(path: str, data: bytes) -> BlobInput:
    framed = f"blob {len(data)}\0".encode("ascii") + data
    return BlobInput(path, hashlib.sha1(framed).hexdigest(), len(data), data)


def call_edges(graph, qname: str):
    source_id = next(s.node_id for s in graph.symbols if s.qualified_name == qname)
    return [e for e in graph.edges if e.edge_type == "CALLS" and e.source_node_id == source_id]


def run(cmd, cwd, *, env=None):
    proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise AssertionError(proc.stderr.decode(errors="replace"))
    return proc.stdout.decode().strip()


def run_bytes(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise AssertionError(proc.stderr.decode(errors="replace"))
    return proc.stdout


def validated_sha40(value: object, label: str) -> str:
    if type(value) is not str:
        raise AssertionError(f"{label} invalid")
    sha = value.lower()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise AssertionError(f"{label} invalid")
    return sha


def optional_sha40_metadata(value: object, label: str) -> str:
    """Render nullable, non-authoritative PR metadata without weakening SHA validation."""
    if value is None:
        return "UNAVAILABLE"
    return validated_sha40(value, label)


def parse_commit_object_identity(raw: bytes) -> tuple[str, tuple[str, ...]]:
    if type(raw) is not bytes:
        raise AssertionError("synthetic merge commit object invalid")
    separator = raw.find(b"\n\n")
    if separator < 0:
        raise AssertionError("synthetic merge commit header invalid")
    header = raw[:separator]
    trees = []
    parents = []
    for line in header.splitlines():
        if line.startswith(b"tree "):
            try:
                value = line[5:].decode("ascii")
            except UnicodeDecodeError as exc:
                raise AssertionError("synthetic merge tree invalid") from exc
            trees.append(validated_sha40(value, "synthetic merge tree"))
        elif line.startswith(b"parent "):
            try:
                value = line[7:].decode("ascii")
            except UnicodeDecodeError as exc:
                raise AssertionError("synthetic merge parent invalid") from exc
            parents.append(validated_sha40(value, "synthetic merge parent"))
        elif line.startswith((b"tree", b"parent")):
            raise AssertionError("synthetic merge commit header invalid")
    if len(trees) != 1:
        raise AssertionError("synthetic merge tree cardinality invalid")
    if len(parents) != 2:
        raise AssertionError("synthetic merge parent cardinality invalid")
    return trees[0], tuple(parents)


def read_commit_object_identity(root: Path, ref: str) -> tuple[str, tuple[str, ...]]:
    return parse_commit_object_identity(run_bytes(["git", "cat-file", "-p", ref], root))


def validated_pr_base_ref(root: Path, value: object) -> str:
    if type(value) is not str or not value or value != value.strip() or len(value) > 255:
        raise AssertionError("pull_request base ref invalid")
    if value.startswith(("-", "refs/")):
        raise AssertionError("pull_request base ref invalid")
    proc = subprocess.run(
        ["git", "check-ref-format", "--branch", value],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise AssertionError("pull_request base ref invalid")
    return value


def resolve_live_base_sha(root: Path, base_ref: object) -> str:
    branch = validated_pr_base_ref(root, base_ref)
    exact_ref = f"refs/heads/{branch}"
    proc = subprocess.run(
        ["git", "ls-remote", "--exit-code", "origin", exact_ref],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise AssertionError("pull_request base ref unavailable on origin")
    rows = [line for line in proc.stdout.decode().splitlines() if line.strip()]
    if len(rows) != 1:
        raise AssertionError("pull_request base ref cardinality invalid")
    fields = rows[0].split()
    if len(fields) != 2 or fields[1] != exact_ref:
        raise AssertionError("pull_request base ref resolution invalid")
    return validated_sha40(fields[0], "pull_request base sha")


def fetch_exact_branch_tree(root: Path, branch_ref: object, expected_sha: object) -> str:
    branch = validated_pr_base_ref(root, branch_ref)
    expected = validated_sha40(expected_sha, "pull_request branch sha")
    exact_ref = f"refs/heads/{branch}"
    verification_ref = "refs/lion/code-perception-head"
    proc = subprocess.run(
        ["git", "fetch", "--no-tags", "--depth=1", "origin", f"{exact_ref}:{verification_ref}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise AssertionError("pull_request branch ref unavailable on origin")
    fetched = validated_sha40(run(["git", "rev-parse", f"{verification_ref}^{{commit}}"], root), "fetched branch sha")
    if fetched != expected:
        raise AssertionError("pull_request branch head drift")
    return validated_sha40(run(["git", "rev-parse", f"{verification_ref}^{{tree}}"], root), "fetched branch tree")


def validate_synthetic_merge_topology(
    *,
    event_base_sha: object,
    live_base_sha: object,
    event_head_sha: object,
    live_head_sha: object,
    workflow_merge_sha: object,
    checked_commit_sha: object,
    parents: tuple[str, ...],
    checked_tree_sha: object,
    candidate_tree_sha: object,
) -> None:
    event_base = validated_sha40(event_base_sha, "event base sha")
    live_base = validated_sha40(live_base_sha, "live base sha")
    event_head = validated_sha40(event_head_sha, "event head sha")
    live_head = validated_sha40(live_head_sha, "live head sha")
    workflow_merge = validated_sha40(workflow_merge_sha, "workflow synthetic merge sha")
    checked_commit = validated_sha40(checked_commit_sha, "checked commit sha")
    checked_tree = validated_sha40(checked_tree_sha, "checked tree sha")
    candidate_tree = validated_sha40(candidate_tree_sha, "candidate tree sha")

    if event_base != live_base:
        raise AssertionError("pull_request base drift")
    if event_head != live_head:
        raise AssertionError("pull_request head drift")
    if workflow_merge != checked_commit:
        raise AssertionError("workflow synthetic merge substitution")
    if len(parents) != 2:
        raise AssertionError("synthetic merge parent cardinality invalid")
    normalized_parents = tuple(validated_sha40(value, "synthetic merge parent") for value in parents)
    if normalized_parents != (event_base, event_head):
        raise AssertionError("synthetic merge parent topology substitution")
    if checked_tree != candidate_tree:
        raise AssertionError("synthetic merge tree substitution")


def blob_inputs_for_ref(root: Path, ref: str) -> tuple[BlobInput, ...]:
    raw = run_bytes(["git", "ls-tree", "-r", "-z", "--long", ref], root)
    result = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path_raw = record.split(b"\t", 1)
        mode, kind, sha_raw, size_raw = meta.split(maxsplit=3)
        if kind != b"blob" or mode not in {b"100644", b"100755", b"120000"}:
            continue
        path = path_raw.decode("utf-8")
        blob_sha = sha_raw.decode("ascii").lower()
        size = int(size_raw)
        data = run_bytes(["git", "cat-file", "blob", blob_sha], root)
        if len(data) != size:
            raise AssertionError(f"blob size mismatch: {path}")
        result.append(BlobInput(path, blob_sha, size, data))
    return tuple(sorted(result, key=lambda item: item.path))


def make_repo(root: Path) -> tuple[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q"], root)
    run(["git", "config", "user.email", "lion@example.invalid"], root)
    run(["git", "config", "user.name", "LION Test"], root)
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("from .a import f\n", encoding="utf-8")
    (root / "pkg" / "a.py").write_text(
        "import os\n\ndef f(x=1):\n    return x\n\nclass C:\n    def m(self):\n        return f()\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    run(["git", "add", "."], root)
    run(["git", "commit", "-q", "-m", "fixture"], root)
    commit = run(["git", "rev-parse", "HEAD"], root)
    tree = run(["git", "rev-parse", "HEAD^{tree}"], root)
    return commit, tree


class CodePerceptionDeterminismTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "source-a"
        self.commit, self.tree = make_repo(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_F01_same_tree_reproducibility_and_F02_order_independence(self):
        one, m1 = build_from_git(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        two, m2 = build_from_git(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        self.assertEqual(one.canonical_bytes(), two.canonical_bytes())
        self.assertEqual(one.digest(), two.digest())
        self.assertEqual(m1.code_graph_digest, m2.code_graph_digest)
        source = git_source_identity(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        reversed_graph = build_code_graph(source, reversed(git_blob_inputs(self.root, source)))
        self.assertEqual(one.canonical_bytes(), reversed_graph.canonical_bytes())

    def test_F03_clock_independence(self):
        one, m1 = build_from_git(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        old = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Pacific/Kiritimati"
            two, m2 = build_from_git(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
        self.assertEqual(one.canonical_bytes(), two.canonical_bytes())
        self.assertEqual(m1.canonical_bytes(), m2.canonical_bytes())

    def test_F04_pythonhashseed_independence_and_F22_byte_canonicality(self):
        package_root = Path(__file__).resolve().parents[2]
        outputs = []
        for seed in ("1", "987654"):
            out = Path(self.temp.name) / f"out-{seed}"
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = str(package_root) + os.pathsep + env.get("PYTHONPATH", "")
            run(
                [
                    sys.executable,
                    "-m",
                    "cyber_lion.enterprise.code_perception_cli",
                    "--repo-root",
                    str(self.root),
                    "--repository",
                    REPOSITORY,
                    "--commit",
                    self.commit,
                    "--expected-tree",
                    self.tree,
                    "--out-dir",
                    str(out),
                ],
                package_root,
                env=env,
            )
            outputs.append((out / "code_graph.json").read_bytes())
        self.assertEqual(outputs[0], outputs[1])

    def test_F05_checkout_root_independence(self):
        other = Path(self.temp.name) / "source-b"
        run(["git", "clone", "-q", "--no-hardlinks", str(self.root), str(other)], Path(self.temp.name))
        one, _ = build_from_git(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        two, _ = build_from_git(other, REPOSITORY, self.commit, expected_tree=self.tree)
        self.assertEqual(one.canonical_bytes(), two.canonical_bytes())
        self.assertEqual(one.digest(), two.digest())

    def test_F14_all_committed_blobs_covered_and_F17_blob_binding(self):
        graph, manifest = build_from_git(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        expected = len(run(["git", "ls-tree", "-r", "--name-only", self.commit], self.root).splitlines())
        self.assertEqual(len(graph.files), expected)
        self.assertEqual(manifest.file_count, expected)
        for file in graph.files:
            self.assertEqual(file.blob_sha, run(["git", "rev-parse", f"{self.commit}:{file.path}"], self.root))

    def test_F15_generated_outputs_do_not_rebind_source_tree(self):
        package_root = Path(__file__).resolve().parents[2]
        out = self.root / "LION" / "code_perception"
        before = run(["git", "rev-parse", f"{self.commit}^{{tree}}"], self.root)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(package_root) + os.pathsep + env.get("PYTHONPATH", "")
        run(
            [
                sys.executable,
                "-m",
                "cyber_lion.enterprise.code_perception_cli",
                "--repo-root",
                str(self.root),
                "--repository",
                REPOSITORY,
                "--commit",
                self.commit,
                "--expected-tree",
                self.tree,
                "--out-dir",
                str(out),
            ],
            package_root,
            env=env,
        )
        after = run(["git", "rev-parse", f"{self.commit}^{{tree}}"], self.root)
        self.assertEqual(before, after)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_tree_sha"], self.tree)
        self.assertTrue(manifest["generated_at_is_non_semantic"])
        self.assertFalse(manifest["authority_effect"])

    def test_F16_source_tree_substitution_fails_closed(self):
        with self.assertRaisesRegex(CodePerceptionBuildError, "source tree substitution"):
            build_from_git(self.root, REPOSITORY, self.commit, expected_tree="f" * 40)

    def test_F25_partial_index_fails_closed_when_blob_disappears(self):
        source = git_source_identity(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        object_path = self.root / ".git" / "objects" / source.source_tree_sha[:2] / source.source_tree_sha[2:]
        if object_path.exists():
            backup = object_path.read_bytes()
            object_path.unlink()
            try:
                with self.assertRaises(CodePerceptionBuildError):
                    git_blob_inputs(self.root, source)
            finally:
                object_path.parent.mkdir(parents=True, exist_ok=True)
                object_path.write_bytes(backup)
        else:
            with self.assertRaises(CodePerceptionBuildError):
                git_source_identity(self.root, REPOSITORY, "0" * 40)

    def test_P0_malformed_and_nonexistent_base_ref_fail_closed(self):
        for value in (None, "", " refs/heads/main", "refs/heads/main", "-main", "bad ref"):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                validated_pr_base_ref(self.root, value)
        run(["git", "remote", "add", "origin", str(self.root)], self.root)
        with self.assertRaisesRegex(AssertionError, "unavailable on origin"):
            resolve_live_base_sha(self.root, "definitely-not-a-branch")

    def test_P0_optional_pr_merge_metadata_is_non_authoritative(self):
        label = "pull_request merge metadata sha"
        self.assertEqual(optional_sha40_metadata(None, label), "UNAVAILABLE")
        self.assertEqual(optional_sha40_metadata("a" * 40, label), "a" * 40)
        for invalid in ("", "not-a-sha", 0, False):
            with self.subTest(value=invalid), self.assertRaises(AssertionError):
                optional_sha40_metadata(invalid, label)

    def test_P0_synthetic_merge_identity_substitutions_fail_closed(self):
        base = "1" * 40
        head = "2" * 40
        merge = "3" * 40
        tree = "4" * 40
        good = {
            "event_base_sha": base,
            "live_base_sha": base,
            "event_head_sha": head,
            "live_head_sha": head,
            "workflow_merge_sha": merge,
            "checked_commit_sha": merge,
            "parents": (base, head),
            "checked_tree_sha": tree,
            "candidate_tree_sha": tree,
        }
        validate_synthetic_merge_topology(**good)
        substitutions = (
            ("event-base", {"event_base_sha": "5" * 40}),
            ("live-base", {"live_base_sha": "5" * 40}),
            ("event-head", {"event_head_sha": "5" * 40}),
            ("live-head", {"live_head_sha": "5" * 40}),
            ("event-synthetic", {"workflow_merge_sha": "5" * 40}),
            ("checked-synthetic", {"checked_commit_sha": "5" * 40}),
            ("synthetic-tree", {"checked_tree_sha": "5" * 40}),
            ("candidate-tree", {"candidate_tree_sha": "5" * 40}),
            ("parent0", {"parents": ("5" * 40, head)}),
            ("parent1", {"parents": (base, "5" * 40)}),
            ("parent-order", {"parents": (head, base)}),
            ("zero-parents", {"parents": ()}),
            ("one-parent", {"parents": (base,)}),
            ("three-parents", {"parents": (base, head, "5" * 40)}),
        )
        for label, substitution in substitutions:
            case = dict(good)
            case.update(substitution)
            with self.subTest(label=label), self.assertRaises(AssertionError):
                validate_synthetic_merge_topology(**case)

    def test_P0_commit_object_header_cardinality_and_malformed_parent_fail_closed(self):
        base = "1" * 40
        head = "2" * 40
        tree = "4" * 40

        def commit_object(*headers: str) -> bytes:
            return ("\n".join(headers) + "\n\nmessage\n").encode("ascii")

        exact_tree, exact_parents = parse_commit_object_identity(
            commit_object(f"tree {tree}", f"parent {base}", f"parent {head}", "author test", "committer test")
        )
        self.assertEqual(exact_tree, tree)
        self.assertEqual(exact_parents, (base, head))

        malformed = (
            ("tree-missing", commit_object(f"parent {base}", f"parent {head}")),
            ("tree-duplicate", commit_object(f"tree {tree}", f"tree {tree}", f"parent {base}", f"parent {head}")),
            ("parent-zero", commit_object(f"tree {tree}")),
            ("parent-one", commit_object(f"tree {tree}", f"parent {base}")),
            ("parent-three", commit_object(f"tree {tree}", f"parent {base}", f"parent {head}", f"parent {'5' * 40}")),
            ("parent-bad-sha", commit_object(f"tree {tree}", "parent not-a-sha", f"parent {head}")),
            ("parent-bad-header", commit_object(f"tree {tree}", f"parent{base}", f"parent {head}")),
        )
        for label, raw in malformed:
            with self.subTest(label=label), self.assertRaises(AssertionError):
                parse_commit_object_identity(raw)

    def test_same_tree_semantic_digest_is_commit_alias_independent(self):
        graph, _ = build_from_git(self.root, REPOSITORY, self.commit, expected_tree=self.tree)
        alias_source = SourceIdentity(REPOSITORY, "f" * 40, self.tree).validate()
        alias_graph = build_code_graph(alias_source, git_blob_inputs(self.root, graph.source))
        self.assertNotEqual(graph.digest(), alias_graph.digest())
        self.assertEqual(tree_semantic_digest(graph), tree_semantic_digest(alias_graph))

    def test_R8_module_call_before_later_definition_is_unresolved(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def caller():\n    return target()\n\ncaller()\n\ndef target():\n    return 1\n"),))
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")

    def test_R8_alias_activation_cannot_make_later_global_exact(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def caller():\n    return target()\n\nf = caller\nf()\n\ndef target():\n    return 1\n"),))
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")

    def test_R8_constructor_activation_cannot_make_later_global_exact(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"class C:\n    def __init__(self):\n        target()\n\nC()\n\ndef target():\n    return 1\n"),))
        call = call_edges(graph, "a.C.__init__")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")

    def test_R8_nested_scope_uses_top_level_activation_floor(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def outer():\n    def inner():\n        return target()\n    return inner()\n\ndef target():\n    return 1\n"),))
        call = call_edges(graph, "a.outer.inner")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")

    def test_R8_earlier_module_definition_may_resolve(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def target():\n    return 1\n\ndef caller():\n    return target()\n\ncaller()\n"),))
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        self.assertEqual(call_edges(graph, "a.caller")[0].target_node_id, target_id)

    def test_R8_later_global_remains_unresolved_even_if_observed_call_is_after_binding(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def caller():\n    return target()\n\ndef target():\n    return 1\n\ncaller()\n"),))
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")
        caller_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.caller")
        module_call = next(e for e in call_edges(graph, "a") if e.target_node_id == caller_id)
        self.assertIsNone(module_call.unresolved_target)

    def test_R8_module_scope_itself_still_respects_call_site_order(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def target():\n    return 1\n\ntarget()\n"),))
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        self.assertEqual(call_edges(graph, "a")[0].target_node_id, target_id)

    def test_R9_cross_scope_global_assignment_poisons_exact_binding(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def target():\n    return 'original'\n\ndef replacement():\n    return 'replacement'\n\ndef caller():\n    return target()\n\ndef mutate():\n    global target\n    target = replacement\n\nmutate()\ncaller()\n"),))
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")

    def test_R9_cross_scope_global_delete_poisons_exact_binding(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def target():\n    return 1\n\ndef caller():\n    return target()\n\ndef mutate():\n    global target\n    del target\n"),))
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")

    def test_R9_cross_scope_global_import_poisons_exact_binding(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (
            fixture_blob("pkg/x.py", b"def f():\n    return 1\n"),
            fixture_blob("pkg/y.py", b"def g():\n    return 2\n"),
            fixture_blob("a.py", b"from pkg.x import f\n\ndef caller():\n    return f()\n\ndef mutate():\n    global f\n    from pkg.y import g as f\n"),
        ))
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "f")

    def test_R9_global_declaration_without_write_does_not_poison(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob("a.py", b"def target():\n    return 1\n\ndef caller():\n    return target()\n\ndef inspect_only():\n    global target\n    return 1\n"),))
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        self.assertEqual(call_edges(graph, "a.caller")[0].target_node_id, target_id)

    def test_R10_globals_dict_rebinding_cannot_turn_static_target_into_runtime_proof(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob(
            "a.py",
            b"def target():\n    return 'original'\n\n"
            b"def replacement():\n    return 'replacement'\n\n"
            b"def caller():\n    return target()\n\n"
            b"globals()['target'] = replacement\ncaller()\n",
        ),))
        call = call_edges(graph, "a.caller")[0]
        self.assertEqual(call.semantic_class, "STATIC_CALL_EVIDENCE")
        self.assertEqual(call.runtime_target_state, "UNRESOLVED")

    def test_R10_exec_rebinding_cannot_turn_static_target_into_runtime_proof(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob(
            "a.py",
            b"def target():\n    return 'original'\n\n"
            b"def caller():\n    return target()\n\n"
            b"exec(\"target=lambda: 'replacement'\")\ncaller()\n",
        ),))
        call = call_edges(graph, "a.caller")[0]
        self.assertEqual(call.semantic_class, "STATIC_CALL_EVIDENCE")
        self.assertEqual(call.runtime_target_state, "UNRESOLVED")

    def test_R10_function_globals_mutation_cannot_turn_static_target_into_runtime_proof(self):
        source = SourceIdentity(REPOSITORY, "1" * 40, "2" * 40).validate()
        graph = build_code_graph(source, (fixture_blob(
            "a.py",
            b"def target():\n    return 'original'\n\n"
            b"def replacement():\n    return 'replacement'\n\n"
            b"def caller():\n    return target()\n\n"
            b"caller.__globals__['target'] = replacement\ncaller()\n",
        ),))
        call = call_edges(graph, "a.caller")[0]
        self.assertEqual(call.semantic_class, "STATIC_CALL_EVIDENCE")
        self.assertEqual(call.runtime_target_state, "UNRESOLVED")

    def test_P1_actual_pr_candidate_projection_is_byte_reproducible(self):
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path:
            self.skipTest("GitHub pull_request event unavailable")
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            self.skipTest("not a pull_request workflow")

        root = Path(__file__).resolve().parents[2]
        expected_head = validated_sha40(pr.get("head", {}).get("sha", ""), "event head sha")
        expected_base = validated_sha40(pr.get("base", {}).get("sha", ""), "event base sha")
        expected_base_ref = validated_pr_base_ref(root, pr.get("base", {}).get("ref"))
        expected_head_ref = validated_pr_base_ref(root, pr.get("head", {}).get("ref"))
        event_merge_metadata = optional_sha40_metadata(pr.get("merge_commit_sha"), "pull_request merge metadata sha")
        workflow_merge = validated_sha40(os.environ.get("GITHUB_SHA", ""), "workflow synthetic merge sha")

        live_base = resolve_live_base_sha(root, expected_base_ref)
        live_head_before = resolve_live_base_sha(root, expected_head_ref)
        candidate_tree = fetch_exact_branch_tree(root, expected_head_ref, expected_head)
        live_head_after = resolve_live_base_sha(root, expected_head_ref)
        if live_head_before != live_head_after:
            raise AssertionError("pull_request head changed during observation")
        checked_commit = validated_sha40(run(["git", "rev-parse", "HEAD"], root), "checked commit sha")
        checked_tree, parents = read_commit_object_identity(root, "HEAD")

        validate_synthetic_merge_topology(
            event_base_sha=expected_base,
            live_base_sha=live_base,
            event_head_sha=expected_head,
            live_head_sha=live_head_after,
            workflow_merge_sha=workflow_merge,
            checked_commit_sha=checked_commit,
            parents=parents,
            checked_tree_sha=checked_tree,
            candidate_tree_sha=candidate_tree,
        )

        source = SourceIdentity(REPOSITORY, expected_head, checked_tree).validate()
        blobs = blob_inputs_for_ref(root, "HEAD")
        first = build_code_graph(source, blobs)
        second = build_code_graph(source, reversed(blobs))
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(len(first.files), len(blobs))
        print(
            "CODE_PERCEPTION_CANDIDATE_PROJECTION "
            f"head={expected_head} tree={checked_tree} digest={first.digest()} "
            f"tree_semantic_digest={tree_semantic_digest(first)} "
            f"files={len(first.files)} symbols={len(first.symbols)} edges={len(first.edges)} "
            f"workflow_merge={workflow_merge} event_merge_metadata={event_merge_metadata}"
        )


if __name__ == "__main__":
    unittest.main()
