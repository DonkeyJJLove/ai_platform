from __future__ import annotations
import ast
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import subprocess
from .model import CanonicalDiagramModel, DiagramNode, DiagramEdge, canonical_projection_identity

_PROJECTIONS = (
    "lion-system-component-map", "authority-and-effect-chain-R17-R22",
    "builder-lifecycle-state-machine", "persistent-authority-store-model",
    "fleet-topology", "evolutionary-epoch-loop", "startup-agent-evolution-loop",
    "repository-mutation-boundaries", "event-and-causality-map", "capability-map",
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def available_projection_names() -> tuple[str, ...]:
    return _PROJECTIONS


def _digest_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class _LexicalCallCollector(ast.NodeVisitor):
    """Collect calls in one lexical function body without descending into nested scopes."""

    def __init__(self) -> None:
        self.bare_names: list[str] = []

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.bare_names.append(node.func.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return None

    def visit_Lambda(self, node: ast.Lambda):
        return None

    def visit_ClassDef(self, node: ast.ClassDef):
        return None


class ArchitectureProjectionExtractor:
    """Static-only canonical projection extractor; analyzed code is never imported or executed."""

    def __init__(self, *, source_tree_sha: str, source_root: str | Path | None = None, source_files: dict[str, str] | None = None):
        self.source_tree_sha = source_tree_sha
        self.source_root = Path(source_root) if source_root is not None else Path.cwd()
        self._source_files_supplied = source_files is not None
        self.source_files = dict(source_files or {})
        self.observed_source_tree_sha: str | None = None
        if not self._source_files_supplied:
            self.observed_source_tree_sha = self._observe_checkout_tree_sha()
            if self.observed_source_tree_sha != self.source_tree_sha:
                raise ValueError(
                    "canonical projection source tree mismatch: "
                    f"expected {self.source_tree_sha}, observed {self.observed_source_tree_sha}"
                )

    def _observe_checkout_tree_sha(self) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.source_root), "rev-parse", "HEAD^{tree}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("canonical projection checkout tree is unobservable") from exc
        observed = result.stdout.strip()
        if not _SHA40.fullmatch(observed):
            raise ValueError("canonical projection checkout tree is invalid")
        return observed

    def _source(self, path: str) -> str:
        if path in self.source_files:
            return self.source_files[path]
        candidate = self.source_root / PurePosixPath(path)
        if not candidate.is_file():
            raise ValueError(f"canonical projection source missing: {path}")
        return candidate.read_text(encoding="utf-8")

    def _symbol_names(self, text: str, path: str) -> set[str]:
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError as exc:
            raise ValueError(f"canonical projection source is not parseable: {path}") from exc
        names: set[str] = set()
        for item in ast.walk(tree):
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(item.name)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                names.add(item.target.id)
        return names

    def _fact(self, *, path: str, label: str, kind: str, token: str | None = None, authority_semantics: str = "NONE") -> DiagramNode:
        text = self._source(path)
        if token is not None:
            names = self._symbol_names(text, path)
            if token not in names and token not in text:
                raise ValueError(f"canonical projection token missing: {path}:{token}")
        node_id = canonical_projection_identity(
            relation_domain="canonical-fact", canonical_source_path=path,
            semantic_kind=kind, qualified_name=label,
        )
        return DiagramNode(node_id, label, kind, path, _digest_text(text), "CANONICAL_FACT", authority_semantics).validate()

    def _frontier(self, label: str) -> DiagramNode:
        node_id = canonical_projection_identity(
            relation_domain="declared-frontier", canonical_source_path="design:R22K",
            semantic_kind="frontier", qualified_name=label,
        )
        return DiagramNode(node_id, label, "frontier", "design:R22K-post-merge", "", "DECLARED_NEXT_FRONTIER", "NONE").validate()

    def _edge(self, a: DiagramNode, b: DiagramNode, relation: str, label: str = "") -> DiagramEdge:
        provenance = a.source_path if a.source_path == b.source_path else f"{a.source_path}->{b.source_path}"
        return DiagramEdge(a.node_id, b.node_id, relation, label, provenance).validate()

    def extract_python(self, files: dict[str, str], *, diagram_id: str = "lion-system-component-map") -> CanonicalDiagramModel:
        nodes: dict[str, DiagramNode] = {}
        edges: set[DiagramEdge] = set()

        def add_node(node: DiagramNode):
            previous = nodes.get(node.node_id)
            if previous is not None and previous != node:
                raise ValueError("projection identity collision")
            nodes[node.node_id] = node

        for path, text in sorted(files.items()):
            if PurePosixPath(path).suffix != ".py":
                continue
            digest = _digest_text(text)
            module_id = canonical_projection_identity(
                relation_domain="python-module", canonical_source_path=path,
                semantic_kind="module", qualified_name=path,
            )
            module = DiagramNode(module_id, path, "module", path, digest).validate()
            add_node(module)
            try:
                tree = ast.parse(text, filename=path)
            except SyntaxError:
                unknown_id = canonical_projection_identity(
                    relation_domain="parse-error", canonical_source_path=path,
                    semantic_kind="unknown", qualified_name="UNKNOWN_PARSE",
                )
                unknown = DiagramNode(unknown_id, "UNKNOWN_PARSE", "unknown", path, digest).validate()
                add_node(unknown)
                edges.add(DiagramEdge(module.node_id, unknown.node_id, "UNKNOWN", "parse-failure").validate())
                continue

            top_level: dict[str, DiagramNode] = {}
            top_level_functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
            for item in tree.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified = f"{PurePosixPath(path).as_posix()}::{item.name}"
                    symbol_id = canonical_projection_identity(
                        relation_domain="python-symbol", canonical_source_path=path,
                        semantic_kind=type(item).__name__, qualified_name=qualified,
                    )
                    symbol = DiagramNode(symbol_id, item.name, type(item).__name__, path, digest).validate()
                    add_node(symbol)
                    if item.name in top_level and top_level[item.name] != symbol:
                        raise ValueError("ambiguous top-level symbol")
                    top_level[item.name] = symbol
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        top_level_functions[item.name] = item
                    edges.add(self._edge(module, symbol, "CONTAINS"))
                elif isinstance(item, ast.Import):
                    for alias in item.names:
                        import_id = canonical_projection_identity(
                            relation_domain="python-import", canonical_source_path=path,
                            semantic_kind="external-module", qualified_name=alias.name,
                        )
                        target = DiagramNode(import_id, alias.name, "external-module", path, digest).validate()
                        add_node(target)
                        edges.add(self._edge(module, target, "IMPORTS"))
                elif isinstance(item, ast.ImportFrom) and item.module:
                    import_id = canonical_projection_identity(
                        relation_domain="python-import", canonical_source_path=path,
                        semantic_kind="external-module", qualified_name=item.module,
                    )
                    target = DiagramNode(import_id, item.module, "external-module", path, digest).validate()
                    add_node(target)
                    edges.add(self._edge(module, target, "IMPORTS"))

            for name, item in top_level_functions.items():
                caller = top_level[name]
                collector = _LexicalCallCollector()
                for statement in item.body:
                    collector.visit(statement)
                for called_name in collector.bare_names:
                    callee = top_level.get(called_name)
                    if callee is not None and called_name in top_level_functions and callee != caller:
                        edges.add(self._edge(caller, callee, "CALLS_STATIC"))

        return CanonicalDiagramModel(
            diagram_id, "component", self.source_tree_sha,
            tuple(sorted(nodes.values())), tuple(sorted(edges)),
        ).validate()

    def named_projection(self, name: str) -> CanonicalDiagramModel:
        if name not in _PROJECTIONS:
            raise ValueError("unknown projection")

        if name == "authority-and-effect-chain-R17-R22":
            specs = (
                ("cyber_lion/contracts/builder_entry_permit.py", "BuilderEntryPermit", "capability", "BuilderEntryPermit"),
                ("cyber_lion/contracts/builder_invocation_permit.py", "BuilderInvocationPermit", "capability", "BuilderInvocationPermit"),
                ("cyber_lion/contracts/builder_invocation_consumption.py", "BuilderInvocationConsumptionPermit", "capability", "BuilderInvocationConsumptionPermit"),
                ("cyber_lion/contracts/builder_start_admission.py", "BuilderStartAdmission", "capability", "BuilderStartAdmission"),
                ("cyber_lion/enterprise/builder_process_launch.py", "BuilderProcessLaunchBoundary", "effect-boundary", "BuilderProcessLaunchBoundary"),
            )
            nodes = [self._fact(path=p, label=l, kind=k, token=t, authority_semantics="REFERENCE_ONLY" if "Permit" in l or "Admission" in l else "NONE") for p, l, k, t in specs]
            nodes.append(self._frontier("BuilderProcessCompletionObservation"))
            edges = tuple(self._edge(a, b, "SOURCE_PROVENANCE") for a, b in zip(nodes, nodes[1:]))
            return CanonicalDiagramModel(name, "sequence", self.source_tree_sha, tuple(sorted(nodes)), tuple(sorted(edges))).validate()

        if name == "builder-lifecycle-state-machine":
            source = "cyber_lion/contracts/builder_process_launch.py"
            states = [
                self._fact(path=source, label="ADMITTED", kind="state", token="BuilderProcessLaunchRequest"),
                self._fact(path=source, label="HELD_NOT_EXECUTING_BUILDER", kind="state", token="HELD_STATE"),
                self._fact(path=source, label="STARTED_OBSERVED", kind="state", token="STARTED_STATE"),
                self._frontier("COMPLETION_UNOBSERVED"),
            ]
            edges = (
                self._edge(states[0], states[1], "EFFECT_BOUNDARY", "prepare"),
                self._edge(states[1], states[2], "EFFECT_BOUNDARY", "commit_start"),
                DiagramEdge(states[2].node_id, states[3].node_id, "UNKNOWN", "next-frontier").validate(),
            )
            return CanonicalDiagramModel(name, "state", self.source_tree_sha, tuple(sorted(states)), tuple(sorted(edges))).validate()

        projection_specs = {
            "persistent-authority-store-model": ("component", "PERSISTENCE_BINDING", (
                ("cyber_lion/enterprise/persistent_authority_state.py", "SQLiteAuthorityStateStore", "SQLiteAuthorityStateStore"),
                ("cyber_lion/enterprise/persistent_authority_state.py", "builder_process_launch_intent", "builder_process_launch_intent"),
                ("cyber_lion/enterprise/persistent_authority_state.py", "builder_process_held_materialization", "builder_process_held_materialization"),
                ("cyber_lion/enterprise/persistent_authority_state.py", "builder_process_launch_receipt", "builder_process_launch_receipt"),
            )),
            "fleet-topology": ("deployment", "FLEET_MEMBERSHIP", (
                ("cyber_lion/enterprise/swarm_governor.py", "SwarmGovernorLeaseStore", "SwarmGovernorLeaseStore"),
                ("cyber_lion/contracts/swarm_governance.py", "SwarmFormation", "SwarmFormation"),
                ("cyber_lion/contracts/swarm_governance.py", "RoleAssignment", "RoleAssignment"),
                ("cyber_lion/contracts/swarm_governance.py", "VERIFIER_ROLE", "VERIFIER"),
            )),
            "evolutionary-epoch-loop": ("state", "EPOCH_TRANSITION", (
                ("cyber_lion/enterprise/evolutionary_epoch.py", "EvolutionaryEpochEngine", "EvolutionaryEpochEngine"),
                ("cyber_lion/enterprise/evolutionary_epoch.py", "EVENT_MAP", "_EVENT_MAP"),
                ("cyber_lion/enterprise/evolutionary_epoch.py", "EPOCH_FORWARD", "_EPOCH_FORWARD"),
                ("cyber_lion/enterprise/evolutionary_epoch.py", "NEXT_EPOCH_CANDIDATE_READY", "NEXT_EPOCH_CANDIDATE_READY"),
            )),
            "startup-agent-evolution-loop": ("component", "EPOCH_TRANSITION", (
                ("cyber_lion/startup_agent/orchestrator.py", "AIDrivenStartupAgent", "AIDrivenStartupAgent"),
                ("cyber_lion/startup_agent/orchestrator.py", "plan", "plan"),
                ("cyber_lion/startup_agent/orchestrator.py", "build_local", "build_local"),
                ("cyber_lion/startup_agent/orchestrator.py", "apply_outcome", "apply_outcome"),
            )),
            "repository-mutation-boundaries": ("component", "SOURCE_PROVENANCE", (
                ("cyber_lion/contracts/repository_mutation.py", "DetachedRepositoryCandidate", "DetachedRepositoryCandidate"),
                ("cyber_lion/enterprise/repository_mutation_pep.py", "RepositoryMutationPEP", "RepositoryMutationPEP"),
                ("cyber_lion/enterprise/repository_mutation_state.py", "RepositoryAttachJournal", "RepositoryAttachJournal"),
            )),
            "event-and-causality-map": ("component", "EVENT_CAUSALITY", (
                ("cyber_lion/contracts/events.py", "EventEnvelope", "EventEnvelope"),
                ("cyber_lion/contracts/events.py", "GateRequested", "GateRequested"),
                ("cyber_lion/contracts/events.py", "GateApplied", "GateApplied"),
                ("cyber_lion/contracts/events.py", "ActionExecuted", "ActionExecuted"),
            )),
            "capability-map": ("component", "CONTAINS", (
                ("cyber_lion/enterprise/conformance.py", "READ_ONLY", "ReadOnlyProviderSnapshot"),
                ("cyber_lion/enterprise/policy_gate.py", "LOCAL_WRITE", "local_write"),
                ("cyber_lion/contracts/builder_process_launch.py", "BUILDER_PROCESS_START", "EFFECT_CLASS"),
                ("cyber_lion/contracts/builder_start_admission.py", "REPOSITORY_REF_MUTATION", "repository_ref_mutation"),
            )),
            "lion-system-component-map": ("component", "CONTAINS", (
                ("cyber_lion/contracts/builder_process_launch.py", "contracts", "BuilderProcessLaunchRequest"),
                ("cyber_lion/enterprise/builder_process_launch.py", "enterprise", "BuilderProcessLaunchBoundary"),
                ("cyber_lion/enterprise/swarm_governor.py", "fleet", "SwarmGovernorLeaseStore"),
                ("cyber_lion/startup_agent/orchestrator.py", "startup_agent", "AIDrivenStartupAgent"),
                ("cyber_lion/enterprise/evolutionary_epoch.py", "evolutionary_epoch", "EvolutionaryEpochEngine"),
            )),
        }
        diagram_type, relation, specs = projection_specs[name]
        nodes = [self._fact(path=p, label=l, kind="component", token=t) for p, l, t in specs]
        edges = tuple(self._edge(a, b, relation) for a, b in zip(nodes, nodes[1:]))
        return CanonicalDiagramModel(name, diagram_type, self.source_tree_sha, tuple(sorted(nodes)), tuple(sorted(edges))).validate()
