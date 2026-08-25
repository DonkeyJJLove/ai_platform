from __future__ import annotations
import ast
from hashlib import sha256
from pathlib import Path, PurePosixPath
from .model import CanonicalDiagramModel, DiagramNode, DiagramEdge, canonical_projection_identity

_PROJECTIONS = (
    "lion-system-component-map",
    "authority-and-effect-chain-R17-R22",
    "builder-lifecycle-state-machine",
    "persistent-authority-store-model",
    "fleet-topology",
    "evolutionary-epoch-loop",
    "startup-agent-evolution-loop",
    "repository-mutation-boundaries",
    "event-and-causality-map",
    "capability-map",
)


def available_projection_names() -> tuple[str, ...]:
    return _PROJECTIONS


def _digest_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class ArchitectureProjectionExtractor:
    """Static-only canonical projection extractor; it never imports analyzed code."""

    def __init__(self, *, source_tree_sha: str, source_root: str | Path | None = None, source_files: dict[str, str] | None = None):
        self.source_tree_sha = source_tree_sha
        self.source_root = Path(source_root) if source_root is not None else Path.cwd()
        self.source_files = dict(source_files or {})

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
            relation_domain="canonical-fact",
            canonical_source_path=path,
            semantic_kind=kind,
            qualified_name=label,
        )
        return DiagramNode(node_id, label, kind, path, _digest_text(text), "CANONICAL_FACT", authority_semantics).validate()

    def _frontier(self, label: str) -> DiagramNode:
        node_id = canonical_projection_identity(
            relation_domain="declared-frontier",
            canonical_source_path="design:R22K",
            semantic_kind="frontier",
            qualified_name=label,
        )
        return DiagramNode(node_id, label, "frontier", "design:R22K-post-merge", "", "DECLARED_NEXT_FRONTIER", "NONE").validate()

    def _edge(self, a: DiagramNode, b: DiagramNode, relation: str, label: str = "") -> DiagramEdge:
        provenance = a.source_path if a.source_path == b.source_path else f"{a.source_path}->{b.source_path}"
        return DiagramEdge(a.node_id, b.node_id, relation, label, provenance).validate()

    def extract_python(self, files: dict[str, str], *, diagram_id: str = "lion-system-component-map") -> CanonicalDiagramModel:
        nodes: dict[str, DiagramNode] = {}
        edges: set[DiagramEdge] = set()
        modules_by_basename: dict[str, DiagramNode] = {}
        local_symbols: dict[str, dict[str, DiagramNode]] = {}

        def add_node(node: DiagramNode):
            previous = nodes.get(node.node_id)
            if previous is not None and previous != node:
                raise ValueError("projection identity collision")
            nodes[node.node_id] = node

        for path, text in sorted(files.items()):
            p = PurePosixPath(path)
            if p.suffix != ".py":
                continue
            mid = canonical_projection_identity(relation_domain="python-module", canonical_source_path=path, semantic_kind="module", qualified_name=path)
            module = DiagramNode(mid, path, "module", path, _digest_text(text)).validate()
            add_node(module)
            modules_by_basename[p.stem] = module
            local_symbols[path] = {}
            try:
                tree = ast.parse(text, filename=path)
            except SyntaxError:
                uid = canonical_projection_identity(relation_domain="parse-error", canonical_source_path=path, semantic_kind="unknown", qualified_name="UNKNOWN_PARSE")
                unknown = DiagramNode(uid, "UNKNOWN_PARSE", "unknown", path, _digest_text(text)).validate()
                add_node(unknown)
                edges.add(DiagramEdge(module.node_id, unknown.node_id, "UNKNOWN", "parse-failure").validate())
                continue
            for item in ast.walk(tree):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified = f"{path}:{item.name}"
                    sid = canonical_projection_identity(relation_domain="python-symbol", canonical_source_path=path, semantic_kind=type(item).__name__, qualified_name=qualified)
                    symbol = DiagramNode(sid, item.name, type(item).__name__, path, _digest_text(text)).validate()
                    add_node(symbol)
                    local_symbols[path][item.name] = symbol
                    edges.add(self._edge(module, symbol, "CONTAINS"))
                elif isinstance(item, ast.Import):
                    for alias in item.names:
                        synthetic_path = f"external:{alias.name}"
                        tid = canonical_projection_identity(relation_domain="python-import", canonical_source_path=path, semantic_kind="external-module", qualified_name=alias.name)
                        target = DiagramNode(tid, alias.name, "external-module", path, _digest_text(text)).validate()
                        add_node(target)
                        edges.add(self._edge(module, target, "IMPORTS"))
                elif isinstance(item, ast.ImportFrom) and item.module:
                    tid = canonical_projection_identity(relation_domain="python-import", canonical_source_path=path, semantic_kind="external-module", qualified_name=item.module)
                    target = DiagramNode(tid, item.module, "external-module", path, _digest_text(text)).validate()
                    add_node(target)
                    edges.add(self._edge(module, target, "IMPORTS"))
            # only direct bare-name calls to exact local definitions are represented as CALLS_STATIC.
            for item in ast.walk(tree):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    caller = local_symbols[path].get(item.name)
                    if caller is None:
                        continue
                    for call in ast.walk(item):
                        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                            callee = local_symbols[path].get(call.func.id)
                            if callee is not None and callee != caller:
                                edges.add(self._edge(caller, callee, "CALLS_STATIC"))
                        elif isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
                            # Attribute/dynamic dispatch remains explicitly unknown.
                            pass
        return CanonicalDiagramModel(diagram_id, "component", self.source_tree_sha, tuple(sorted(nodes.values())), tuple(sorted(edges))).validate()

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
            text = self._source(source)
            states = []
            for label, token in (("ADMITTED", "BuilderProcessLaunchRequest"), ("HELD_NOT_EXECUTING_BUILDER", "HELD_STATE"), ("STARTED_OBSERVED", "STARTED_STATE")):
                states.append(self._fact(path=source, label=label, kind="state", token=token))
            states.append(self._frontier("COMPLETION_UNOBSERVED"))
            edges = (
                self._edge(states[0], states[1], "EFFECT_BOUNDARY", "prepare"),
                self._edge(states[1], states[2], "EFFECT_BOUNDARY", "commit_start"),
                DiagramEdge(states[2].node_id, states[3].node_id, "UNKNOWN", "next-frontier").validate(),
            )
            return CanonicalDiagramModel(name, "state", self.source_tree_sha, tuple(sorted(states)), tuple(sorted(edges))).validate()

        projection_specs = {
            "persistent-authority-store-model": (
                "component", "PERSISTENCE_BINDING",
                (("cyber_lion/enterprise/persistent_authority_state.py", "SQLiteAuthorityStateStore", "SQLiteAuthorityStateStore"),
                 ("cyber_lion/enterprise/persistent_authority_state.py", "builder_process_launch_intent", "builder_process_launch_intent"),
                 ("cyber_lion/enterprise/persistent_authority_state.py", "builder_process_held_materialization", "builder_process_held_materialization"),
                 ("cyber_lion/enterprise/persistent_authority_state.py", "builder_process_launch_receipt", "builder_process_launch_receipt")),
            ),
            "fleet-topology": (
                "deployment", "FLEET_MEMBERSHIP",
                (("cyber_lion/enterprise/swarm_governor.py", "SwarmGovernor", "SwarmGovernor"),
                 ("cyber_lion/contracts/swarm_governance.py", "Formation", "Formation"),
                 ("cyber_lion/contracts/swarm_governance.py", "Drone", "Drone"),
                 ("cyber_lion/contracts/swarm_governance.py", "Verifier", "Verifier")),
            ),
            "evolutionary-epoch-loop": (
                "state", "EPOCH_TRANSITION",
                (("cyber_lion/enterprise/evolutionary_epoch.py", "observe", "observe"),
                 ("cyber_lion/enterprise/evolutionary_epoch.py", "hypothesize", "hypothesize"),
                 ("cyber_lion/enterprise/evolutionary_epoch.py", "falsify", "falsify"),
                 ("cyber_lion/enterprise/evolutionary_epoch.py", "promote", "promote"),
                 ("cyber_lion/enterprise/evolutionary_epoch.py", "next-epoch", "next_epoch")),
            ),
            "startup-agent-evolution-loop": (
                "component", "EPOCH_TRANSITION",
                (("cyber_lion/startup_agent/orchestrator.py", "Explore", "Explore"),
                 ("cyber_lion/startup_agent/orchestrator.py", "Experiment", "Experiment"),
                 ("cyber_lion/startup_agent/orchestrator.py", "Build", "Build"),
                 ("cyber_lion/startup_agent/orchestrator.py", "Learn", "Learn")),
            ),
            "repository-mutation-boundaries": (
                "component", "SOURCE_PROVENANCE",
                (("cyber_lion/contracts/repository_mutation.py", "CandidateVerification", "CandidateVerification"),
                 ("cyber_lion/enterprise/repository_mutation_pep.py", "RepositoryMutationPEP", "RepositoryMutationPEP"),
                 ("cyber_lion/enterprise/repository_mutation_state.py", "RepositoryMutationState", "RepositoryMutationState")),
            ),
            "event-and-causality-map": (
                "component", "EVENT_CAUSALITY",
                (("cyber_lion/contracts/events.py", "EventEnvelope", "EventEnvelope"),
                 ("cyber_lion/contracts/events.py", "GateRequested", "GateRequested"),
                 ("cyber_lion/contracts/events.py", "GateApplied", "GateApplied"),
                 ("cyber_lion/contracts/events.py", "ExecutionReceipt", "ExecutionReceipt")),
            ),
            "capability-map": (
                "component", "CONTAINS",
                (("cyber_lion/contracts/capability.py", "READ_ONLY", "READ_ONLY"),
                 ("cyber_lion/contracts/capability.py", "LOCAL_WRITE", "LOCAL_WRITE"),
                 ("cyber_lion/contracts/builder_process_launch.py", "BUILDER_PROCESS_START", "EFFECT_CLASS"),
                 ("cyber_lion/contracts/repository_mutation.py", "REPOSITORY_REF_MUTATION", "REPOSITORY_REF_MUTATION")),
            ),
            "lion-system-component-map": (
                "component", "CONTAINS",
                (("cyber_lion/contracts/builder_process_launch.py", "contracts", "BuilderProcessLaunchRequest"),
                 ("cyber_lion/enterprise/builder_process_launch.py", "enterprise", "BuilderProcessLaunchBoundary"),
                 ("cyber_lion/enterprise/swarm_governor.py", "fleet", "SwarmGovernor"),
                 ("cyber_lion/startup_agent/orchestrator.py", "startup_agent", "Orchestrator"),
                 ("cyber_lion/enterprise/evolutionary_epoch.py", "evolutionary_epoch", "Epoch")),
            ),
        }
        diagram_type, relation, specs = projection_specs[name]
        nodes = [self._fact(path=p, label=l, kind="component", token=t) for p, l, t in specs]
        edges = tuple(self._edge(a, b, relation) for a, b in zip(nodes, nodes[1:]))
        return CanonicalDiagramModel(name, diagram_type, self.source_tree_sha, tuple(sorted(nodes)), tuple(sorted(edges))).validate()
