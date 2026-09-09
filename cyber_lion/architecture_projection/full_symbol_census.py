"""Deterministic full committed-Python symbol census for LION v1.4.

The census is source-derived evidence only. It does not execute Git, import inspected
modules, infer runtime call targets, mint authority, or claim that a static test
reference proves execution coverage. The caller must supply the exact committed
Python path set and exact Git HEAD/TREE identities.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping, Sequence

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_MATERIAL_MARKER = re.compile(
    r"(?:authority|runtime|effect|currentness|reconcil|policy|admission|execution|"
    r"fence|permit|grant|credential|secret|token)",
    re.IGNORECASE,
)
_TEST_PATH = re.compile(r"(?:^|/)(?:tests?|test_[^/]*)/")
_ENUM_BASES = frozenset({"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"})
_PROTOCOL_BASES = frozenset({"Protocol"})
_EXCEPTION_BASES = frozenset({"BaseException", "Exception"})


class FullSymbolCensusError(ValueError):
    """Raised when the committed-source census cannot be constructed exactly."""


def _sha40(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise FullSymbolCensusError(f"{label} must be exact lowercase SHA-1")
    return value


def _canonical_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise FullSymbolCensusError("committed Python path is not canonical")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise FullSymbolCensusError("committed Python path is not canonical")
    if path.suffix != ".py":
        raise FullSymbolCensusError("committed census path must end in .py")
    return path.as_posix()


def _expr_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError, TypeError):
        return ast.dump(node, include_attributes=False)


def _tail_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _call_name(node: ast.Call) -> str:
    def walk(value: ast.AST) -> str:
        if isinstance(value, ast.Name):
            return value.id
        if isinstance(value, ast.Attribute):
            left = walk(value.value)
            return f"{left}.{value.attr}" if left else value.attr
        return ""

    return walk(node.func)


def _is_test_path(path: str) -> bool:
    return path.startswith("tests/") or "/tests/" in f"/{path}" or bool(_TEST_PATH.search(path)) or PurePosixPath(path).name.startswith("test_")


def _module_name(path: str) -> str:
    pure = PurePosixPath(path)
    parts = list(pure.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else "__init__"


def _is_public_name(name: str) -> bool:
    return bool(name) and not name.startswith("_")


def _function_annotation_state(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[bool, bool]:
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        args.append(node.args.vararg)
    if node.args.kwarg is not None:
        args.append(node.args.kwarg)
    relevant = [arg for arg in args if arg.arg not in {"self", "cls"}]
    has_any = node.returns is not None or any(arg.annotation is not None for arg in relevant)
    fully = node.returns is not None and all(arg.annotation is not None for arg in relevant)
    return has_any, fully


def _class_annotation_state(node: ast.ClassDef) -> tuple[bool, bool]:
    direct = [item for item in node.body if isinstance(item, (ast.Assign, ast.AnnAssign))]
    if not direct:
        return False, False
    has_any = any(isinstance(item, ast.AnnAssign) and item.annotation is not None for item in direct)
    fully = all(isinstance(item, ast.AnnAssign) and item.annotation is not None for item in direct)
    return has_any, fully


@dataclass(frozen=True)
class CensusSymbol:
    path: str
    module: str
    qualified_name: str
    leaf_name: str
    kind: str
    start_line: int
    end_line: int
    public: bool
    private_material_symbol: bool
    private_material_reason: tuple[str, ...]
    docstring_present: bool
    any_type_annotation_present: bool
    fully_annotated_signature_or_fields: bool
    dataclass: bool
    protocol: bool
    enum: bool
    exception: bool
    decorators: tuple[str, ...]
    inheritance: tuple[str, ...]
    static_calls: tuple[str, ...]
    authority_related_lexical: bool
    runtime_related_lexical: bool
    effect_surface_refs: tuple[str, ...]
    test_reference_candidates: tuple[str, ...]


@dataclass(frozen=True)
class CensusFile:
    path: str
    module: str
    source_sha256: str
    parse_state: str
    module_docstring_present: bool
    imports: tuple[str, ...]
    symbol_count: int
    public_symbol_count: int


class _ModuleCollector(ast.NodeVisitor):
    def __init__(self, *, path: str, module: str) -> None:
        self.path = path
        self.module = module
        self.stack: list[tuple[str, str]] = []
        self.symbol_nodes: list[tuple[str, str, ast.AST]] = []
        self.imports: set[str] = set()

    def _qname(self, name: str) -> str:
        prefix = ".".join(item[0] for item in self.stack)
        return f"{self.module}.{prefix}.{name}" if prefix else f"{self.module}.{name}"

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        prefix = "." * node.level + (node.module or "")
        for alias in node.names:
            self.imports.add(f"{prefix}:{alias.name}")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbol_nodes.append((self._qname(node.name), "CLASS", node))
        self.stack.append((node.name, "CLASS"))
        self.generic_visit(node)
        self.stack.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, async_kind: bool) -> None:
        in_class = bool(self.stack and self.stack[-1][1] == "CLASS")
        if async_kind:
            kind = "ASYNC_METHOD" if in_class else "ASYNC_FUNCTION"
        else:
            kind = "METHOD" if in_class else "FUNCTION"
        self.symbol_nodes.append((self._qname(node.name), kind, node))
        self.stack.append((node.name, kind))
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, async_kind=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, async_kind=True)


class _StaticTestReferenceCollector(ast.NodeVisitor):
    def __init__(self, *, path: str) -> None:
        self.path = path
        self.current_test = ""
        self.references: dict[str, set[str]] = {}

    def _record(self, name: str) -> None:
        if self.current_test and name:
            self.references.setdefault(name, set()).add(f"{self.path}:{self.current_test}")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        previous = self.current_test
        if node.name.startswith("test"):
            self.current_test = node.name
        self.generic_visit(node)
        self.current_test = previous

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        previous = self.current_test
        if node.name.startswith("test"):
            self.current_test = node.name
        self.generic_visit(node)
        self.current_test = previous

    def visit_Name(self, node: ast.Name) -> None:
        self._record(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._record(node.attr)
        self.generic_visit(node)


def _symbol_calls(node: ast.AST) -> tuple[str, ...]:
    values = {_call_name(item) for item in ast.walk(node) if isinstance(item, ast.Call)}
    return tuple(sorted(value for value in values if value))


def _symbol_flags(node: ast.AST) -> tuple[bool, bool, bool, bool, tuple[str, ...], tuple[str, ...]]:
    if not isinstance(node, ast.ClassDef):
        decorators = tuple(sorted(_expr_text(item) for item in getattr(node, "decorator_list", ())))
        return False, False, False, False, decorators, ()
    decorators = tuple(sorted(_expr_text(item) for item in node.decorator_list))
    inheritance = tuple(_expr_text(item) for item in node.bases)
    tails = {_tail_name(item) for item in node.bases}
    dataclass_flag = any(_tail_name(item) == "dataclass" for item in node.decorator_list)
    protocol_flag = bool(tails & _PROTOCOL_BASES)
    enum_flag = bool(tails & _ENUM_BASES)
    exception_flag = bool(tails & _EXCEPTION_BASES) or any(
        name.endswith("Error") or name.endswith("Exception") for name in tails if name
    )
    return dataclass_flag, protocol_flag, enum_flag, exception_flag, decorators, inheritance


def _source_for_symbol(source: str, node: ast.AST) -> str:
    lines = source.splitlines()
    start = max(getattr(node, "lineno", 1) - 1, 0)
    end = min(getattr(node, "end_lineno", getattr(node, "lineno", 1)), len(lines))
    return "\n".join(lines[start:end])


def _effect_refs_by_symbol(
    symbols: Sequence[tuple[str, str, ast.AST]],
    surface_refs: Sequence[str],
) -> Mapping[str, tuple[str, ...]]:
    lines: list[tuple[int, str]] = []
    for ref in surface_refs:
        parts = ref.split(":", 2)
        if len(parts) >= 2 and parts[1].isdigit():
            lines.append((int(parts[1]), ref))
    result: dict[str, tuple[str, ...]] = {}
    for qname, _kind, node in symbols:
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", start)
        refs = tuple(sorted(ref for line, ref in lines if start <= line <= end))
        if refs:
            result[qname] = refs
    return result


def build_full_symbol_census(
    *,
    source_root: str | Path,
    committed_python_paths: Iterable[str],
    source_head: str,
    source_tree: str,
) -> Mapping[str, object]:
    """Build an exact deterministic census from the supplied committed Python set."""
    head = _sha40(source_head, "source_head")
    tree_sha = _sha40(source_tree, "source_tree")
    root = Path(source_root).resolve()
    if not root.is_dir():
        raise FullSymbolCensusError("source_root must be an existing directory")
    normalized = [_canonical_path(value) for value in committed_python_paths]
    if len(normalized) != len(set(normalized)):
        raise FullSymbolCensusError("committed Python path set contains duplicates")
    paths = tuple(sorted(normalized, key=lambda value: value.encode("utf-8")))
    if not paths:
        raise FullSymbolCensusError("committed Python path set cannot be empty")

    sources: dict[str, str] = {}
    parsed: dict[str, ast.Module] = {}
    collectors: dict[str, _ModuleCollector] = {}
    files: list[CensusFile] = []
    parse_failures: list[Mapping[str, str]] = []
    test_refs_by_leaf: dict[str, set[str]] = {}

    for path in paths:
        candidate = root.joinpath(*PurePosixPath(path).parts)
        if candidate.is_symlink():
            parse_failures.append({"path": path, "error": "SYMLINK_NOT_PARSED"})
            continue
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            parse_failures.append({"path": path, "error": "SOURCE_PATH_UNAVAILABLE_OR_ESCAPED"})
            continue
        try:
            raw = resolved.read_bytes()
            source = raw.decode("utf-8", "strict")
        except (OSError, UnicodeError):
            parse_failures.append({"path": path, "error": "SOURCE_READ_OR_UTF8_ERROR"})
            continue
        try:
            module_ast = ast.parse(source, filename=path, type_comments=True)
        except SyntaxError as exc:
            parse_failures.append({"path": path, "error": f"SYNTAX_ERROR:{exc.lineno or 0}:{exc.offset or 0}"})
            continue
        module = _module_name(path)
        collector = _ModuleCollector(path=path, module=module)
        collector.visit(module_ast)
        sources[path] = source
        parsed[path] = module_ast
        collectors[path] = collector
        if _is_test_path(path):
            refs = _StaticTestReferenceCollector(path=path)
            refs.visit(module_ast)
            for leaf, values in refs.references.items():
                test_refs_by_leaf.setdefault(leaf, set()).update(values)
        files.append(
            CensusFile(
                path=path,
                module=module,
                source_sha256=sha256(raw).hexdigest(),
                parse_state="PARSED",
                module_docstring_present=ast.get_docstring(module_ast, clean=False) is not None,
                imports=tuple(sorted(collector.imports)),
                symbol_count=len(collector.symbol_nodes),
                public_symbol_count=sum(
                    1 for qname, _kind, _node in collector.symbol_nodes if _is_public_name(qname.rsplit(".", 1)[-1])
                ),
            )
        )

    scanner_inventory = None
    if sources:
        scanner_inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision=head,
            tree_digest=tree_sha,
            sources=sources,
        )
    surfaces_by_path: dict[str, list[str]] = {}
    surface_records: list[Mapping[str, object]] = []
    unclassified_effect_refs: tuple[str, ...] = ()
    if scanner_inventory is not None:
        unclassified_effect_refs = tuple(scanner_inventory.unclassified_refs)
        for surface in scanner_inventory.surfaces:
            payload = {
                "surface_id": surface.surface_id,
                "effect_class": surface.effect_class,
                "authority_class": surface.authority_class,
                "implementation_refs": list(surface.implementation_refs),
                "entrypoints": list(surface.entrypoints),
            }
            surface_records.append(payload)
            for implementation_ref in surface.implementation_refs:
                surfaces_by_path.setdefault(implementation_ref, []).extend(surface.entrypoints)

    symbols: list[CensusSymbol] = []
    for path in sorted(parsed, key=lambda value: value.encode("utf-8")):
        source = sources[path]
        collector = collectors[path]
        effect_by_qname = _effect_refs_by_symbol(collector.symbol_nodes, surfaces_by_path.get(path, ()))
        for qname, kind, node in collector.symbol_nodes:
            leaf = qname.rsplit(".", 1)[-1]
            dataclass_flag, protocol_flag, enum_flag, exception_flag, decorators, inheritance = _symbol_flags(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                any_annotation, full_annotation = _function_annotation_state(node)
            elif isinstance(node, ast.ClassDef):
                any_annotation, full_annotation = _class_annotation_state(node)
            else:
                any_annotation, full_annotation = False, False
            symbol_source = _source_for_symbol(source, node)
            effect_refs = effect_by_qname.get(qname, ())
            material_reasons: list[str] = []
            public = _is_public_name(leaf)
            if not public and effect_refs:
                material_reasons.append("CONTAINS_EFFECT_SURFACE")
            if not public and _MATERIAL_MARKER.search(f"{path} {qname} {symbol_source}"):
                material_reasons.append("LEXICAL_BOUNDARY_MARKER")
            symbols.append(
                CensusSymbol(
                    path=path,
                    module=_module_name(path),
                    qualified_name=qname,
                    leaf_name=leaf,
                    kind=kind,
                    start_line=getattr(node, "lineno", 1),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                    public=public,
                    private_material_symbol=bool(material_reasons),
                    private_material_reason=tuple(sorted(set(material_reasons))),
                    docstring_present=ast.get_docstring(node, clean=False) is not None,
                    any_type_annotation_present=any_annotation,
                    fully_annotated_signature_or_fields=full_annotation,
                    dataclass=dataclass_flag,
                    protocol=protocol_flag,
                    enum=enum_flag,
                    exception=exception_flag,
                    decorators=decorators,
                    inheritance=inheritance,
                    static_calls=_symbol_calls(node),
                    authority_related_lexical=bool(re.search(r"authority|grant|permit|credential|policy|pdp", f"{path} {qname}", re.I)),
                    runtime_related_lexical=bool(re.search(r"runtime|execution|effect|reconcil|admission|sandbox|fence", f"{path} {qname}", re.I)),
                    effect_surface_refs=tuple(effect_refs),
                    test_reference_candidates=tuple(sorted(test_refs_by_leaf.get(leaf, ()))) if not _is_test_path(path) else (),
                )
            )

    files_sorted = tuple(sorted(files, key=lambda item: item.path.encode("utf-8")))
    symbols_sorted = tuple(sorted(symbols, key=lambda item: (item.path.encode("utf-8"), item.start_line, item.qualified_name)))
    public_symbols = tuple(item for item in symbols_sorted if item.public)
    private_material = tuple(item for item in symbols_sorted if item.private_material_symbol)
    counts = {
        "committed_python_files": len(paths),
        "parsed_python_files": len(files_sorted),
        "parse_failures": len(parse_failures),
        "modules": len(files_sorted),
        "classes": sum(item.kind == "CLASS" for item in symbols_sorted),
        "dataclasses": sum(item.dataclass for item in symbols_sorted),
        "protocols": sum(item.protocol for item in symbols_sorted),
        "enums": sum(item.enum for item in symbols_sorted),
        "exceptions": sum(item.exception for item in symbols_sorted),
        "functions": sum(item.kind == "FUNCTION" for item in symbols_sorted),
        "async_functions": sum(item.kind == "ASYNC_FUNCTION" for item in symbols_sorted),
        "methods": sum(item.kind in {"METHOD", "ASYNC_METHOD"} for item in symbols_sorted),
        "symbols": len(symbols_sorted),
        "public_symbols": len(public_symbols),
        "private_material_symbols": len(private_material),
        "documented_public_symbols": sum(item.docstring_present for item in public_symbols),
        "documented_private_material_symbols": sum(item.docstring_present for item in private_material),
        "symbols_with_any_type_annotation": sum(item.any_type_annotation_present for item in symbols_sorted),
        "effect_surfaces_in_python": len(surface_records),
        "unclassified_effect_refs_in_python": len(unclassified_effect_refs),
        "authority_related_symbols_lexical": sum(item.authority_related_lexical for item in symbols_sorted),
        "runtime_related_symbols_lexical": sum(item.runtime_related_lexical for item in symbols_sorted),
    }
    coverage = {
        "public_docstring_percentage": round((counts["documented_public_symbols"] / counts["public_symbols"] * 100.0), 6) if counts["public_symbols"] else 100.0,
        "private_material_docstring_percentage": round((counts["documented_private_material_symbols"] / counts["private_material_symbols"] * 100.0), 6) if counts["private_material_symbols"] else 100.0,
        "parse_coverage_percentage": round((counts["parsed_python_files"] / counts["committed_python_files"] * 100.0), 6),
    }
    result: dict[str, object] = {
        "schema_version": "lion.full-symbol-census/v1.4-r22c-1",
        "epistemic_class": "DETERMINISTIC_STATIC_SOURCE_EVIDENCE",
        "authority_effect": "NONE",
        "runtime_execution": "NONE",
        "source": {"head": head, "tree": tree_sha},
        "classification_rules": {
            "public_symbol": "leaf name does not start with underscore",
            "private_material_symbol": "private symbol contains a discovered effect surface or lexical boundary marker; conservative static candidate, not runtime authority proof",
            "test_reference_candidate": "test function statically references a unique leaf name; reference is not execution/coverage proof",
            "authority_runtime_flags": "lexical source classification only",
        },
        "counts": counts,
        "coverage": coverage,
        "parse_failures": sorted(parse_failures, key=lambda item: item["path"].encode("utf-8")),
        "files": [asdict(item) for item in files_sorted],
        "symbols": [asdict(item) for item in symbols_sorted],
        "effect_surfaces": sorted(surface_records, key=lambda item: str(item["surface_id"])),
        "unclassified_effect_refs": list(unclassified_effect_refs),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    result["census_digest"] = sha256(b"LION/FULL-SYMBOL-CENSUS/1\0" + canonical).hexdigest()
    result["success"] = not parse_failures and counts["parsed_python_files"] == counts["committed_python_files"]
    return result


def canonical_census_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _read_zlist(path: Path) -> tuple[str, ...]:
    raw = path.read_bytes()
    parts = raw.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    try:
        return tuple(part.decode("utf-8", "strict") for part in parts)
    except UnicodeError as exc:
        raise FullSymbolCensusError("path list must be UTF-8") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic LION full Python symbol census")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--paths-zlist", required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args(argv)
    payload = build_full_symbol_census(
        source_root=args.source_root,
        committed_python_paths=_read_zlist(Path(args.paths_zlist)),
        source_head=args.source_head,
        source_tree=args.source_tree,
    )
    print(canonical_census_json(payload), end="")
    return 0 if payload["success"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
