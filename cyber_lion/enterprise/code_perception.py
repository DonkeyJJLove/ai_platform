"""Deterministic whole-repository code perception for the SEM plane.

The indexer binds exact Git commit/tree/blob identity and uses only Python stdlib
``ast`` + ``symtable`` for Python semantics. Facts are deterministic evidence only.
Named lexical scopes are modeled conservatively; anonymous scopes (lambda and
comprehensions) are explicit resolution barriers until separately modeled.
Call resolution produces source-derived static call evidence only; it never proves the
callable selected by a future Python runtime. Control-flow, dynamic-dispatch, mutable
attribute, and global-binding filters improve static candidate precision without
creating a closed-world runtime claim. Exact runtime targets require separate runtime
observation evidence outside this source indexer.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import subprocess
import symtable
from typing import Iterable

from cyber_lion.contracts.code_perception import (
    CodeEdge,
    CodeGraph,
    FileRecord,
    PerceptionManifest,
    SourceIdentity,
    SymbolRecord,
    stable_digest,
)
from cyber_lion.contracts.enterprise_graph import canonical_json

GENERATOR_VERSION = "2.0.0"
_ANON_SCOPE_TYPES = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_NAMED_SCOPE_TYPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


class CodePerceptionBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class BlobInput:
    path: str
    blob_sha: str
    size: int
    data: bytes


@dataclass(frozen=True)
class _Binding:
    kind: str
    target: str
    position: tuple[int, int]


@dataclass
class _Scope:
    node: ast.AST
    table: symtable.SymbolTable
    symbol: SymbolRecord
    qname: str
    parent: "_Scope | None"
    bindings: dict[str, tuple[_Binding, ...]]
    assigned_names: frozenset[str]


@dataclass
class _Parsed:
    file: FileRecord
    module_name: str
    module_node: SymbolRecord
    tree: ast.Module
    node_qnames: dict[int, str]
    node_symbols: dict[int, SymbolRecord]
    is_package: bool
    parent_map: dict[int, ast.AST]
    scope_by_node: dict[int, _Scope]
    module_scope: _Scope


# --------------------------- Git / source identity ---------------------------

def _git(repo_root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise CodePerceptionBuildError("git executable unavailable") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace")[:1000]
        raise CodePerceptionBuildError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout


def git_source_identity(
    repo_root: str | Path,
    repository: str,
    commit: str,
    *,
    expected_tree: str | None = None,
) -> SourceIdentity:
    root = Path(repo_root)
    commit_sha = _git(root, "rev-parse", f"{commit}^{{commit}}").decode().strip().lower()
    tree_sha = _git(root, "rev-parse", f"{commit_sha}^{{tree}}").decode().strip().lower()
    source = SourceIdentity(repository, commit_sha, tree_sha).validate()
    if expected_tree is not None and tree_sha != expected_tree.lower():
        raise CodePerceptionBuildError("source tree substitution detected")
    return source


def git_blob_inputs(repo_root: str | Path, source: SourceIdentity) -> tuple[BlobInput, ...]:
    root = Path(repo_root)
    source.validate()
    raw = _git(root, "ls-tree", "-r", "-z", "--long", source.source_commit_sha)
    entries: list[tuple[str, str, int]] = []
    seen_paths: set[str] = set()
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            meta, path_raw = record.split(b"\t", 1)
            mode, kind, blob_raw, size_raw = meta.split(maxsplit=3)
            path = path_raw.decode("utf-8")
            blob_sha = blob_raw.decode("ascii").lower()
            size = int(size_raw)
        except Exception as exc:
            raise CodePerceptionBuildError("malformed git tree inventory") from exc
        if kind != b"blob" or mode not in {b"100644", b"100755", b"120000"}:
            continue
        if path in seen_paths:
            raise CodePerceptionBuildError("duplicate path in git inventory")
        seen_paths.add(path)
        entries.append((path, blob_sha, size))

    inputs: list[BlobInput] = []
    for path, blob_sha, size in sorted(entries):
        data = _git(root, "cat-file", "blob", blob_sha)
        if len(data) != size:
            raise CodePerceptionBuildError(f"blob size mismatch: {path}")
        actual = _git(root, "hash-object", "--stdin", input_bytes=data).decode().strip().lower()
        if actual != blob_sha:
            raise CodePerceptionBuildError(f"blob substitution detected: {path}")
        inputs.append(BlobInput(path, blob_sha, size, data))
    if len(inputs) != len(entries):
        raise CodePerceptionBuildError("partial repository index")
    return tuple(inputs)


# --------------------------- deterministic records ---------------------------

def _language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".md": "markdown",
        ".toml": "toml",
        ".sh": "shell",
        ".ps1": "powershell",
    }.get(suffix, "other")


def _module_name(path: str) -> tuple[str, bool]:
    if not path.endswith(".py"):
        raise CodePerceptionBuildError("module name requested for non-Python file")
    raw = path[:-3].replace("/", ".")
    is_package = raw.endswith(".__init__") or raw == "__init__"
    if raw == "__init__":
        return "__root__", True
    if raw.endswith(".__init__"):
        raw = raw[: -len(".__init__")]
    return raw, is_package


def _file_record(source: SourceIdentity, blob: BlobInput, parse_state: str) -> FileRecord:
    return FileRecord(
        repository=source.repository,
        source_commit_sha=source.source_commit_sha,
        source_tree_sha=source.source_tree_sha,
        file_id=stable_digest("file", blob.path, blob.blob_sha),
        path=blob.path,
        blob_sha=blob.blob_sha,
        language=_language(blob.path),
        size=blob.size,
        parse_state=parse_state,
    ).validate()


def _node_range(node: ast.AST, *, line_count: int) -> tuple[int, int, int, int]:
    start_line = int(getattr(node, "lineno", 1) or 1)
    start_col = int(getattr(node, "col_offset", 0) or 0)
    end_line = int(getattr(node, "end_lineno", start_line) or start_line)
    end_col = int(getattr(node, "end_col_offset", start_col) or start_col)
    if isinstance(node, ast.Module):
        start_line, start_col, end_line, end_col = 1, 0, max(1, line_count), 0
    return start_line, start_col, end_line, end_col


def _signature(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ast.dump(node.args, annotate_fields=True, include_attributes=False)
    if isinstance(node, ast.ClassDef):
        bases = [ast.dump(base, annotate_fields=True, include_attributes=False) for base in node.bases]
        return canonical_json(bases).decode("utf-8")
    return ""


def _semantic_digest(node: ast.AST) -> str:
    return sha256(ast.dump(node, annotate_fields=True, include_attributes=False).encode("utf-8")).hexdigest()


def _symbol(file: FileRecord, kind: str, qname: str, node: ast.AST, line_count: int) -> SymbolRecord:
    a, b, c, d = _node_range(node, line_count=line_count)
    return SymbolRecord(
        node_id=stable_digest("symbol", file.path, qname, kind),
        kind=kind,
        qualified_name=qname,
        file_id=file.file_id,
        blob_sha=file.blob_sha,
        start_line=a,
        start_col=b,
        end_line=c,
        end_col=d,
        signature=_signature(node),
        semantic_digest=_semantic_digest(node),
        path=file.path,
    ).validate()


def _evidence(blob_sha: str, node: ast.AST, *, line_count: int) -> str:
    a, b, c, d = _node_range(node, line_count=line_count)
    return f"blob:{blob_sha}:L{a}:C{b}-L{c}:C{d}"


def _edge(edge_type: str, source: str, target: str | None, unresolved: str | None, evidence: str) -> CodeEdge:
    identity = target if target is not None else "?" + str(unresolved)
    return CodeEdge(
        edge_id=stable_digest("edge", edge_type, source, identity, evidence),
        edge_type=edge_type,
        source_node_id=source,
        target_node_id=target,
        unresolved_target=unresolved,
        evidence_ref=evidence,
    ).validate()


def _definition_kind(node: ast.AST, in_class: bool) -> str:
    if isinstance(node, ast.ClassDef):
        return "CLASS"
    if isinstance(node, ast.AsyncFunctionDef):
        return "ASYNC_METHOD" if in_class else "ASYNC_FUNCTION"
    return "METHOD" if in_class else "FUNCTION"


# ------------------------------- AST topology --------------------------------

def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    result: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            result[id(child)] = parent
    return result


def _nearest_definition_parent(node: ast.AST, parent_map: dict[int, ast.AST]) -> ast.AST | None:
    cur = parent_map.get(id(node))
    while cur is not None:
        if isinstance(cur, _DEF_TYPES):
            return cur
        cur = parent_map.get(id(cur))
    return None


def _nearest_named_scope_node(node: ast.AST, parent_map: dict[int, ast.AST]) -> ast.AST:
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, _NAMED_SCOPE_TYPES):
            return cur
        cur = parent_map.get(id(cur))
    raise CodePerceptionBuildError("AST node has no named lexical scope")


def _anonymous_boundary_between(
    node: ast.AST,
    scope_node: ast.AST,
    parent_map: dict[int, ast.AST],
) -> ast.AST | None:
    cur: ast.AST | None = node
    while cur is not None and cur is not scope_node:
        if isinstance(cur, _ANON_SCOPE_TYPES):
            return cur
        cur = parent_map.get(id(cur))
    return None


def _is_direct_scope_statement(node: ast.AST, scope_node: ast.AST, parent_map: dict[int, ast.AST]) -> bool:
    """True only for statements directly in the named scope body.

    A syntactic definition/import nested under If/For/While/Try/Match/With is a
    source fact, but not proof that its runtime binding exists on every path that can
    reach a later call. P1 therefore admits exact bindings only for direct statements.
    """
    return parent_map.get(id(node)) is scope_node


def _collect_definitions(
    file: FileRecord,
    module_name: str,
    tree: ast.Module,
    line_count: int,
    parent_map: dict[int, ast.AST],
) -> tuple[tuple[SymbolRecord, ...], dict[int, str], dict[int, SymbolRecord]]:
    module_symbol = _symbol(file, "MODULE", module_name, tree, line_count)
    symbols: list[SymbolRecord] = [module_symbol]
    qnames: dict[int, str] = {id(tree): module_name}
    node_symbols: dict[int, SymbolRecord] = {id(tree): module_symbol}
    defs = [n for n in ast.walk(tree) if isinstance(n, _DEF_TYPES)]

    def depth(node: ast.AST) -> int:
        value = 0
        cur = _nearest_definition_parent(node, parent_map)
        while cur is not None:
            value += 1
            cur = _nearest_definition_parent(cur, parent_map)
        return value

    defs.sort(key=lambda n: (depth(n), int(getattr(n, "lineno", 0) or 0), int(getattr(n, "col_offset", 0) or 0), n.name))
    for node in defs:
        parent = _nearest_definition_parent(node, parent_map)
        if parent is None:
            parent_qname, in_class = module_name, False
        else:
            parent_qname = qnames.get(id(parent))
            if parent_qname is None:
                raise CodePerceptionBuildError("definition parent qname missing")
            in_class = isinstance(parent, ast.ClassDef)
        qname = f"{parent_qname}.{node.name}"
        symbol = _symbol(file, _definition_kind(node, in_class), qname, node, line_count)
        symbols.append(symbol)
        qnames[id(node)] = qname
        node_symbols[id(node)] = symbol
    return tuple(symbols), qnames, node_symbols


# ------------------------------- scope model --------------------------------

def _scope_child_table(parent: symtable.SymbolTable, node: ast.AST) -> symtable.SymbolTable:
    expected_type = "class" if isinstance(node, ast.ClassDef) else "function"
    name = getattr(node, "name", "")
    line = int(getattr(node, "lineno", 0) or 0)
    candidates = [
        child for child in parent.get_children()
        if child.get_type() == expected_type and child.get_name() == name and int(child.get_lineno()) == line
    ]
    if len(candidates) != 1:
        raise CodePerceptionBuildError(f"symtable scope mapping ambiguous: {expected_type}:{name}:{line}")
    return candidates[0]


def _scope_events(
    scope_node: ast.AST,
    parent_map: dict[int, ast.AST],
    module_name: str,
    is_package: bool,
    qnames: dict[int, str],
) -> tuple[dict[str, tuple[_Binding, ...]], frozenset[str]]:
    bindings: dict[str, list[_Binding]] = {}
    assigned: set[str] = set()

    def exact_scope(node: ast.AST) -> bool:
        if _nearest_named_scope_node(node, parent_map) is not scope_node:
            return False
        return _anonymous_boundary_between(node, scope_node, parent_map) is None

    def bind(name: str, kind: str, target: str, node: ast.AST) -> None:
        bindings.setdefault(name, []).append(
            _Binding(kind, target, (int(getattr(node, "lineno", 0) or 0), int(getattr(node, "col_offset", 0) or 0)))
        )

    for node in ast.walk(scope_node):
        if isinstance(node, _DEF_TYPES) and node is not scope_node:
            if _is_direct_scope_statement(node, scope_node, parent_map):
                qname = qnames.get(id(node))
                if qname is not None:
                    bind(node.name, "DEFINITION", qname, node)
            continue
        if node is not scope_node and not exact_scope(node):
            continue

        if isinstance(node, ast.Import):
            if not _is_direct_scope_statement(node, scope_node, parent_map):
                continue
            for item in node.names:
                local = item.asname or item.name.split(".")[0]
                target = item.name if item.asname else item.name.split(".")[0]
                bind(local, "IMPORT", target, node)
        elif isinstance(node, ast.ImportFrom):
            if not _is_direct_scope_statement(node, scope_node, parent_map):
                continue
            parts = module_name.split(".") if is_package else module_name.split(".")[:-1]
            if node.level:
                pops = max(0, node.level - 1)
                if pops > len(parts):
                    continue
                if pops:
                    parts = parts[:-pops]
            elif node.module:
                parts = []
            if node.module:
                parts += node.module.split(".")
            base = ".".join(p for p in parts if p)
            for item in node.names:
                if item.name == "*":
                    continue
                bind(item.asname or item.name, "IMPORT", f"{base}.{item.name}" if base else item.name, node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            assigned.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and isinstance(node.name, str):
            assigned.add(node.name)

    normalized = {
        name: tuple(sorted(items, key=lambda b: (b.position, b.kind, b.target)))
        for name, items in sorted(bindings.items())
    }
    return normalized, frozenset(sorted(assigned))


def _build_scopes(
    tree: ast.Module,
    text: str,
    path: str,
    module_name: str,
    is_package: bool,
    qnames: dict[int, str],
    node_symbols: dict[int, SymbolRecord],
    parent_map: dict[int, ast.AST],
) -> tuple[dict[int, _Scope], _Scope]:
    try:
        root_table = symtable.symtable(text, path, "exec")
    except (SyntaxError, ValueError, TypeError) as exc:
        raise CodePerceptionBuildError("symtable parse failed") from exc

    scope_by_node: dict[int, _Scope] = {}
    node_by_id = {id(n): n for n in ast.walk(tree)}

    def build(node: ast.AST, table: symtable.SymbolTable, parent: _Scope | None) -> _Scope:
        symbol = node_symbols.get(id(node))
        qname = qnames.get(id(node))
        if symbol is None or qname is None:
            raise CodePerceptionBuildError("scope deterministic identity missing")
        bindings, assigned = _scope_events(node, parent_map, module_name, is_package, qnames)
        scope = _Scope(node, table, symbol, qname, parent, bindings, assigned)
        scope_by_node[id(node)] = scope
        expected_parent = None if isinstance(node, ast.Module) else node
        children = [
            child for child_id in node_symbols
            for child in [node_by_id.get(child_id)]
            if child is not None and isinstance(child, _DEF_TYPES)
            and _nearest_definition_parent(child, parent_map) is expected_parent
        ]
        children.sort(key=lambda n: (int(getattr(n, "lineno", 0) or 0), int(getattr(n, "col_offset", 0) or 0), n.name))
        for child in children:
            build(child, _scope_child_table(table, child), scope)
        return scope

    root = build(tree, root_table, None)
    return scope_by_node, root


def _scope_for_node(node: ast.AST, parsed: _Parsed) -> _Scope:
    named = _nearest_named_scope_node(node, parsed.parent_map)
    scope = parsed.scope_by_node.get(id(named))
    if scope is None:
        raise CodePerceptionBuildError("lexical scope mapping missing")
    return scope


def _execution_scope(node: ast.AST, parsed: _Parsed) -> _Scope:
    scope = _scope_for_node(node, parsed)
    if isinstance(scope.node, ast.Module):
        return scope
    cur: ast.AST = node
    while parsed.parent_map.get(id(cur)) is not scope.node:
        parent = parsed.parent_map.get(id(cur))
        if parent is None:
            return scope.parent or parsed.module_scope
        cur = parent
    # Function/class body executes in its own scope. Signature/default/decorator/base
    # expressions execute in the enclosing scope.
    if cur in getattr(scope.node, "body", ()):
        return scope
    return scope.parent or parsed.module_scope


def _module_activation_floor(scope: _Scope, parsed: _Parsed) -> tuple[int, int] | None:
    """Earliest conservative module-init boundary for an executable named scope."""
    if scope is parsed.module_scope:
        return None
    cur = scope
    while cur.parent is not None and cur.parent is not parsed.module_scope:
        cur = cur.parent
    if cur.parent is not parsed.module_scope:
        return None
    return (
        int(getattr(cur.node, "lineno", 0) or 0),
        int(getattr(cur.node, "col_offset", 0) or 0),
    )


def _cross_scope_module_global_writes(parsed: _Parsed) -> frozenset[str]:
    """Names that another named scope can explicitly write into module globals.

    This is a conservative static-candidate filter, not a proof that unlisted Python
    reflection or external mutation cannot alter the runtime binding.
    """
    cached = getattr(parsed, "_cross_scope_global_writes_cache", None)
    if cached is not None:
        return cached
    names: set[str] = set()
    for scope in parsed.scope_by_node.values():
        if scope is parsed.module_scope:
            continue
        candidates = set(scope.assigned_names) | set(scope.bindings)
        for name in sorted(candidates):
            try:
                symbol = scope.table.lookup(name)
            except KeyError:
                continue
            if symbol.is_global():
                names.add(name)
    result = frozenset(sorted(names))
    setattr(parsed, "_cross_scope_global_writes_cache", result)
    return result


def _single_binding(
    scope: _Scope,
    name: str,
    qname_index: dict[str, str],
    *,
    at_position: tuple[int, int] | None,
) -> tuple[str | None, str | None]:
    if name in scope.assigned_names:
        return None, None
    values = scope.bindings.get(name, ())
    if len(values) != 1:
        return None, None
    binding = values[0]
    if at_position is not None and not (binding.position < at_position):
        return None, None
    if binding.kind == "DEFINITION":
        return qname_index.get(binding.target), binding.target
    if binding.kind == "IMPORT":
        return None, binding.target
    return None, None


def _module_binding(
    name: str,
    execution_scope: _Scope,
    parsed: _Parsed,
    qname_index: dict[str, str],
) -> tuple[str | None, str | None]:
    values = parsed.module_scope.bindings.get(name, ())
    if name in parsed.module_scope.assigned_names or len(values) != 1:
        return None, None
    if name in _cross_scope_module_global_writes(parsed):
        return None, None
    binding = values[0]
    floor = _module_activation_floor(execution_scope, parsed)
    if floor is not None and not (binding.position < floor):
        return None, None
    return _single_binding(parsed.module_scope, name, qname_index, at_position=None)


def _root_binding(
    name: str,
    scope: _Scope,
    parsed: _Parsed,
    qname_index: dict[str, str],
    *,
    at_position: tuple[int, int],
) -> tuple[str | None, str | None]:
    try:
        symbol = scope.table.lookup(name)
    except KeyError:
        return None, None
    if symbol.is_parameter() or symbol.is_nonlocal() or symbol.is_free():
        return None, None
    if name in scope.assigned_names:
        return None, None
    if scope is not parsed.module_scope and symbol.is_global():
        return _module_binding(name, scope, parsed, qname_index)
    return _single_binding(scope, name, qname_index, at_position=at_position)


def _resolve_name(
    raw: str,
    scope: _Scope,
    parsed: _Parsed,
    qname_index: dict[str, str],
    *,
    at_position: tuple[int, int],
) -> str | None:
    first, dot, rest = raw.partition(".")
    if first in {"self", "cls"} and dot:
        return None
    direct, prefix = _root_binding(first, scope, parsed, qname_index, at_position=at_position)
    if not dot:
        return direct or (qname_index.get(prefix) if prefix else None)
    if prefix is None:
        return None
    return qname_index.get(f"{prefix}.{rest}")


def _expr_name(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        prefix = _expr_name(expr.value)
        return f"{prefix}.{expr.attr}" if prefix else None
    return None


# --------------------------------- edges -------------------------------------

def _build_edges(parsed_modules: tuple[_Parsed, ...], symbols: tuple[SymbolRecord, ...]) -> tuple[CodeEdge, ...]:
    qname_index = {s.qualified_name: s.node_id for s in symbols}
    module_index = {p.module_name: p.module_node.node_id for p in parsed_modules}
    edges: list[CodeEdge] = []

    for parsed in parsed_modules:
        line_count = max(1, parsed.module_node.end_line)
        edges.append(_edge("CONTAINS", parsed.file.file_id, parsed.module_node.node_id, None, f"blob:{parsed.file.blob_sha}:module"))
        for symbol in parsed.node_symbols.values():
            if symbol.node_id == parsed.module_node.node_id:
                continue
            parent_qname = symbol.qualified_name.rsplit(".", 1)[0]
            parent_id = qname_index.get(parent_qname, parsed.module_node.node_id)
            edges.append(_edge("DEFINES", parent_id, symbol.node_id, None, f"blob:{parsed.file.blob_sha}:define:{symbol.qualified_name}"))

        for node in ast.walk(parsed.tree):
            evidence = _evidence(parsed.file.blob_sha, node, line_count=line_count)
            scope = _execution_scope(node, parsed)
            source_symbol = scope.symbol

            if isinstance(node, ast.Import):
                for item in node.names:
                    target = module_index.get(item.name)
                    edges.append(_edge("IMPORTS", source_symbol.node_id, target, None if target else item.name, evidence + f":{item.name}"))

            elif isinstance(node, ast.ImportFrom):
                parts = parsed.module_name.split(".") if parsed.is_package else parsed.module_name.split(".")[:-1]
                if node.level:
                    pops = max(0, node.level - 1)
                    if pops > len(parts):
                        parts = []
                    elif pops:
                        parts = parts[:-pops]
                elif node.module:
                    parts = []
                if node.module:
                    parts += node.module.split(".")
                raw = ".".join(parts)
                if raw:
                    target = module_index.get(raw)
                    edges.append(_edge("IMPORTS", source_symbol.node_id, target, None if target else raw, evidence))

            elif isinstance(node, _DEF_TYPES):
                symbol = parsed.node_symbols.get(id(node))
                if symbol is None:
                    continue
                enclosing_node = parsed.parent_map.get(id(node), parsed.tree)
                enclosing_scope = _scope_for_node(enclosing_node, parsed)
                for decorator in node.decorator_list:
                    raw = _expr_name(decorator) or ast.dump(decorator, include_attributes=False)
                    target = None if _anonymous_boundary_between(decorator, enclosing_scope.node, parsed.parent_map) else _resolve_name(
                        raw, enclosing_scope, parsed, qname_index,
                        at_position=(int(getattr(decorator, "lineno", 0) or 0), int(getattr(decorator, "col_offset", 0) or 0)),
                    )
                    edges.append(_edge("DECORATED_BY", symbol.node_id, target, None if target else raw, _evidence(parsed.file.blob_sha, decorator, line_count=line_count)))
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        raw = _expr_name(base) or ast.dump(base, include_attributes=False)
                        target = None if _anonymous_boundary_between(base, enclosing_scope.node, parsed.parent_map) else _resolve_name(
                            raw, enclosing_scope, parsed, qname_index,
                            at_position=(int(getattr(base, "lineno", 0) or 0), int(getattr(base, "col_offset", 0) or 0)),
                        )
                        edges.append(_edge("INHERITS", symbol.node_id, target, None if target else raw, _evidence(parsed.file.blob_sha, base, line_count=line_count)))

            elif isinstance(node, ast.Call):
                raw = _expr_name(node.func)
                if raw:
                    named_scope = _scope_for_node(node, parsed)
                    if _anonymous_boundary_between(node, named_scope.node, parsed.parent_map) is not None:
                        target = None
                    elif isinstance(node.func, ast.Attribute):
                        target = None
                    else:
                        target = _resolve_name(
                            raw, scope, parsed, qname_index,
                            at_position=(int(getattr(node, "lineno", 0) or 0), int(getattr(node, "col_offset", 0) or 0)),
                        )
                    edges.append(_edge("CALLS", source_symbol.node_id, target, None if target else raw, evidence))

    unique: dict[str, CodeEdge] = {}
    for edge in edges:
        previous = unique.get(edge.edge_id)
        if previous is not None and previous != edge:
            raise CodePerceptionBuildError("edge id collision")
        unique[edge.edge_id] = edge
    return tuple(sorted(unique.values(), key=lambda e: (e.edge_type, e.source_node_id, e.target_node_id or "", e.unresolved_target or "", e.evidence_ref, e.edge_id)))


# ------------------------------ public builder -------------------------------

def build_code_graph(source: SourceIdentity, blobs: Iterable[BlobInput]) -> CodeGraph:
    source.validate()
    ordered = sorted(tuple(blobs), key=lambda item: item.path)
    if len({item.path for item in ordered}) != len(ordered):
        raise CodePerceptionBuildError("duplicate blob path")

    files: list[FileRecord] = []
    parsed: list[_Parsed] = []
    symbols: list[SymbolRecord] = []

    for blob in ordered:
        import hashlib
        framed = f"blob {len(blob.data)}\0".encode("ascii") + blob.data
        if hashlib.sha1(framed, usedforsecurity=False).hexdigest() != blob.blob_sha:
            raise CodePerceptionBuildError(f"blob substitution detected: {blob.path}")
        if len(blob.data) != blob.size:
            raise CodePerceptionBuildError(f"blob size mismatch: {blob.path}")
        if not blob.path.endswith(".py"):
            files.append(_file_record(source, blob, "NOT_APPLICABLE"))
            continue
        try:
            text = blob.data.decode("utf-8")
            tree = ast.parse(text, filename=blob.path, type_comments=True)
        except (UnicodeDecodeError, SyntaxError, ValueError, TypeError) as exc:
            files.append(_file_record(source, blob, f"PARSE_ERROR:{type(exc).__name__}"))
            continue

        file = _file_record(source, blob, "PARSED")
        files.append(file)
        module_name, is_package = _module_name(blob.path)
        line_count = max(1, len(text.splitlines()))
        parents = _parent_map(tree)
        module_symbols, qnames, node_symbols = _collect_definitions(file, module_name, tree, line_count, parents)
        module_node = next(s for s in module_symbols if s.kind == "MODULE")
        scope_by_node, module_scope = _build_scopes(tree, text, blob.path, module_name, is_package, qnames, node_symbols, parents)
        symbols.extend(module_symbols)
        parsed.append(_Parsed(file, module_name, module_node, tree, qnames, node_symbols, is_package, parents, scope_by_node, module_scope))

    symbols_tuple = tuple(sorted(symbols, key=lambda s: (s.path, s.qualified_name, s.kind, s.node_id)))
    if len({s.node_id for s in symbols_tuple}) != len(symbols_tuple):
        raise CodePerceptionBuildError("duplicate symbol id collision")
    graph = CodeGraph(
        schema_version="1.0.0",
        source=source,
        files=tuple(sorted(files, key=lambda f: (f.path, f.blob_sha))),
        symbols=symbols_tuple,
        edges=_build_edges(tuple(parsed), symbols_tuple),
        authority_effect=False,
    ).validate()
    if len(graph.files) != len(ordered):
        raise CodePerceptionBuildError("partial repository index")
    return graph


def projection_digest(graph: CodeGraph) -> str:
    return graph.digest()


def tree_semantic_digest(graph: CodeGraph) -> str:
    graph.validate()
    # Use the same logical payload as the projection digest so R10 call semantics
    # (semantic_class/runtime_target_state/call_semantics_version) are tree-bound too;
    # normalize only commit identity to preserve same-tree alias equivalence.
    payload = dict(graph.logical_payload())
    payload["source"]["source_commit_sha"] = "TREE_BOUND"
    for record in payload["files"]:
        record["source_commit_sha"] = "TREE_BOUND"
    return sha256(canonical_json(payload)).hexdigest()


def generator_digest() -> str:
    here = Path(__file__).resolve()
    contract = (here.parents[1] / "contracts" / "code_perception.py").resolve()
    payload = b"code_perception-generator-v1\0" + contract.read_bytes() + b"\0" + here.read_bytes()
    return sha256(payload).hexdigest()


def manifest_for(graph: CodeGraph) -> PerceptionManifest:
    graph.validate()
    python_files = [f for f in graph.files if f.language == "python"]
    parsed = [f for f in python_files if f.parse_state == "PARSED"]
    errors = [f for f in python_files if f.parse_state.startswith("PARSE_ERROR:")]
    return PerceptionManifest(
        schema_version="1.0.0",
        repository=graph.source.repository,
        source_commit_sha=graph.source.source_commit_sha,
        source_tree_sha=graph.source.source_tree_sha,
        generator_version=GENERATOR_VERSION,
        generator_digest=generator_digest(),
        file_count=len(graph.files),
        python_file_count=len(python_files),
        parsed_python_file_count=len(parsed),
        parse_error_count=len(errors),
        symbol_count=len(graph.symbols),
        edge_count=len(graph.edges),
        code_graph_digest=projection_digest(graph),
        generated_at_is_non_semantic=True,
        authority_effect=False,
    ).validate(graph)


def build_from_git(
    repo_root: str | Path,
    repository: str,
    commit: str,
    *,
    expected_tree: str | None = None,
) -> tuple[CodeGraph, PerceptionManifest]:
    source = git_source_identity(repo_root, repository, commit, expected_tree=expected_tree)
    graph = build_code_graph(source, git_blob_inputs(repo_root, source))
    return graph, manifest_for(graph)


def graph_schema_document() -> dict:
    return {
        "schema_version": "1.0.0",
        "call_semantics_version": "2.0.0",
        "plane": "SEM/CODE_PERCEPTION",
        "fact_origin": "DETERMINISTIC",
        "authority_effect": False,
        "edge_types": ["CALLS", "CONTAINS", "DECORATED_BY", "DEFINES", "IMPORTS", "INHERITS"],
        "deferred_edge_types": ["TESTS", "WORKFLOW_INVOKES"],
        "resolution_engine": ["python-stdlib-ast", "python-stdlib-symtable"],
        "call_resolution": "source-derived-static-call-candidate-resolution",
        "calls_semantic_class": "STATIC_CALL_EVIDENCE",
        "calls_target_node_id_semantics": "source-derived-static-candidate-not-runtime-proof",
        "calls_runtime_target_state": "UNRESOLVED",
        "runtime_target_proof_class": "RuntimeCallTargetProof/EXACT_RUNTIME_CALL_TARGET",
        "runtime_target_proof_generated_by_source_indexer": False,
        "runtime_target_proof_requires": [
            "exact-source-commit-tree",
            "exact-code-graph-digest",
            "exact-call-edge",
            "runtime-target-symbol",
            "independent-observer-reference",
            "runtime-evidence-digest",
        ],
        "open_world_policy": "no-closed-world-runtime-target-claim-from-source-analysis",
        "anonymous_scope_policy": "lambda-and-comprehensions-are-unresolved-static-candidate-barriers",
        "anonymous_scope_types": ["Lambda", "ListComp", "SetComp", "DictComp", "GeneratorExp"],
        "attribute_call_policy": "attribute-calls-have-no-exact-static-target-without-separate-binding-model",
        "control_flow_binding_policy": "only-direct-unconditional-scope-definitions-and-imports-are-static-binding-candidates",
        "module_initialization_policy": "module-global-static-candidate-must-precede-top-level-named-scope-activation-floor",
        "module_global_mutation_policy": "explicit-cross-scope-global-writes-poison-static-candidate-only-not-runtime-proof",
        "projection_digest_semantics": "includes-source-commit-tree-and-explicit-call-semantics",
        "tree_semantic_digest_semantics": "normalizes-only-source-commit-identity-and-preserves-call-semantics",
        "same_tree_invariant": "same-repository-tree-blobs-generator=>same-tree-semantic-digest",
    }


def empty_analysis_document(source: SourceIdentity, code_graph_digest: str) -> dict:
    source.validate()
    return {
        "schema_version": "1.0.0",
        "plane": "SEM/SHARED_ANALYSIS",
        "source": {
            "repository": source.repository,
            "source_commit_sha": source.source_commit_sha,
            "source_tree_sha": source.source_tree_sha,
            "code_graph_digest": code_graph_digest,
        },
        "records": [],
        "promotion_state": "DEFERRED_UNTIL_P1_VERIFIED",
        "authority_effect": False,
    }
