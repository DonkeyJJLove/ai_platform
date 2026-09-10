# LION — pełne źródło narzędzia kontenerowego

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

## Status i zakres

Nowe narzędzie pakowania; nie jest implementacją runtime LION i nie zastępuje oryginalnych walidatorów z plików 29/30. Jest kodem do lokalnego, jawnego uruchomienia. Biblioteka standardowa Python; brak sieci, subprocess, shell i wykonywania wyekstrahowanych payloadów. Polecenia extract/rebuild zapisują tylko nowy, wskazany lokalny katalog i odmawiają nadpisania istniejącego.

SOURCE_NAME=lion_rag_tool.py
SOURCE_BYTES=25830
SOURCE_SHA256=8245ee3352bb8b371facad17708233088bb6fd0d4afdbe5977ad46802c0137c7

## Użycie

```text
python lion_rag_tool.py verify LION_PROJECT_RAG32_v1_4_r1
python lion_rag_tool.py self-test LION_PROJECT_RAG32_v1_4_r1
python lion_rag_tool.py locate LION_PROJECT_RAG32_v1_4_r1 AutonomyBlueprint
python lion_rag_tool.py compare LION_PROJECT_RAG32_v1_4_r1 "LION_SYSTEM_v1_3(1).zip" v13
python lion_rag_tool.py extract LION_PROJECT_RAG32_v1_4_r1 recovered_lion_sources
python lion_rag_tool.py rebuild recovered_lion_sources/bundle_recipe.json recovered_lion_sources/sources rebuilt_lion_rag32
```

`rebuild` odtwarza kontenery deterministycznie z jawnego recipe. Nie aktualizuje sam architektury ani dowodów. Zmieniona treść źródła wymaga nowej, przejrzanej rewizji z nową tożsamością/manifestem i spójną aktualizacją warstwy sterującej. Odmowa odbudowy po niezadeklarowanej edycji jest oczekiwanym wynikiem.

## Pełny kod

````python
#!/usr/bin/env python3
"""Offline LION RAG32 integrity, extraction and deterministic rebuilding.

Standard library only. No network, shell, subprocess, imports of extracted code,
repository writes or execution of source payloads. SHA-256 proves byte identity,
not authenticity, live currentness, semantic truth or permission to act.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

FORMAT = "lion.rag-container/v1"
PROFILE = "LION-RAG32/1"
MANIFEST = "05_PACKAGE_MANIFEST.md"
STATE = "03_STATE_AND_CONTINUATION.md"
CASES = "06_VALIDATION_AND_RETRIEVAL.md"
BEGIN = b"LION_RECORD_BEGIN: "
META = b"LION_RECORD_META: "
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_FILE_BYTES = 262144
MAX_SOURCE_BYTES = 262144

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result

def load_json(data: bytes | str) -> Any:
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))

def safe_relative(name: str) -> PurePosixPath:
    if type(name) is not str or not name or "\\" in name or "\x00" in name or ":" in name:
        raise ValueError("invalid relative path")
    p = PurePosixPath(name)
    if p.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError("unsafe relative path")
    return p

def section(data: bytes, tag: str) -> Any:
    opening = f"LION_DATA_BEGIN: {tag}\n```json\n".encode()
    closing = f"\n```\nLION_DATA_END: {tag}".encode()
    if data.count(opening) != 1:
        raise ValueError(f"unique {tag} section required")
    start = data.index(opening) + len(opening)
    end = data.find(closing, start)
    if end < 0:
        raise ValueError(f"unterminated {tag}")
    return load_json(data[start:end])

def json_section(data: Any, tag: str) -> str:
    return (f"LION_DATA_BEGIN: {tag}\n```json\n"
            + json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
            + f"\n```\nLION_DATA_END: {tag}\n")

def fence_for(data: bytes) -> str:
    runs = re.findall(rb"`+", data)
    return "`" * max(4, 1 + max((len(run) for run in runs), default=0))

def render_record(meta: dict[str, Any], data: bytes) -> bytes:
    sid = meta["source_id"]
    f = fence_for(data)
    header = (f'\n<a id="{meta["anchor"]}"></a>\n'
              f"## {sid} — {meta['virtual_path']}\n\n"
              f"SOURCE_ID={sid}\nSOURCE_ARCHIVE={meta['archive_id']}\n"
              f"SOURCE_PATH={meta['original_path']}\n"
              f"SOURCE_CLASS={meta['source_class']}\n"
              f"CURRENTNESS={meta['currentness']}\n"
              "CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER\n"
              f"SOURCE_SHA256={meta['sha256']}\nSOURCE_BYTES={meta['bytes']}\n\n"
              f"LION_RECORD_BEGIN: {sid}\n"
              + "LION_RECORD_META: " + canonical(meta).decode("utf-8") + "\n"
              + f + meta["language"] + "\n").encode("utf-8")
    return header + data + f"\n{f}\nLION_RECORD_END: {sid}\n".encode()

def parse_records(raw: bytes) -> list[tuple[dict[str, Any], bytes]]:
    """Length-delimited parsing; payload markers cannot become new records."""
    output = []
    pos = 0
    while True:
        start = raw.find(BEGIN, pos)
        if start < 0:
            break
        if start and raw[start - 1:start] != b"\n":
            raise ValueError("source marker must start a line")
        end = raw.find(b"\n", start)
        sid = raw[start + len(BEGIN):end].decode("utf-8")
        mstart = end + 1
        mend = raw.find(b"\n", mstart)
        if not raw[mstart:mend].startswith(META):
            raise ValueError("record metadata missing")
        meta = load_json(raw[mstart + len(META):mend])
        if type(meta) is not dict or meta.get("source_id") != sid:
            raise ValueError("record identity mismatch")
        size = meta.get("bytes")
        if type(size) is not int or not 0 <= size <= MAX_SOURCE_BYTES:
            raise ValueError("record length invalid")
        fend = raw.find(b"\n", mend + 1)
        fence_line = raw[mend + 1:fend]
        match = re.fullmatch(rb"(`{4,})([a-z0-9_-]+)", fence_line)
        if match is None or match[2].decode() != meta.get("language"):
            raise ValueError("record fence invalid")
        pstart = fend + 1
        data = raw[pstart:pstart + size]
        suffix = b"\n" + match[1] + f"\nLION_RECORD_END: {sid}\n".encode()
        pend = pstart + size
        if raw[pend:pend + len(suffix)] != suffix:
            raise ValueError("record boundary/length mismatch")
        if fence_for(data).encode() != match[1]:
            raise ValueError("noncanonical outer fence")
        data.decode("utf-8", "strict")
        if digest(data) != meta.get("sha256"):
            raise ValueError("record payload digest mismatch")
        output.append((meta, data))
        pos = pend + len(suffix)
    return output

def source_digest(sources: list[dict[str, Any]]) -> str:
    vector = [{k: s[k] for k in ("source_id", "virtual_path", "sha256", "bytes")}
              for s in sorted(sources, key=lambda x: x["source_id"])]
    return digest(b"LION/RAG-SOURCE-VECTOR/1\0" + canonical(vector))

def file_vector(root: Path) -> list[dict[str, Any]]:
    return [{"path": p.name, "bytes": p.stat().st_size, "sha256": digest(p.read_bytes())}
            for p in sorted(root.iterdir()) if p.is_file() and p.name != MANIFEST]

def seal(root: Path, manifest: dict[str, Any]) -> None:
    m = copy.deepcopy(manifest)
    m["files"] = file_vector(root)
    m["package_content_digest"] = digest(b"LION/RAG-FILES/1\0" + canonical(m["files"]))
    m["source_vector_digest"] = source_digest(m["sources"])
    text = (f"# LION — manifest pakietu\n\nPROFILE_ID={PROFILE}\n"
            f"RELEASE_ID={m['release_id']}\nPACKAGE_AUTHORITY=NONE\n\n"
            "Manifest obejmuje wszystkie pozostałe pliki. Nie hashuje sam siebie. "
            "Zewnętrzny hash ZIP-a jest w raporcie dostawy.\n\n"
            + json_section(m, "PACKAGE_MANIFEST"))
    (root / MANIFEST).write_bytes(text.encode("utf-8"))

def verify(root: Path) -> tuple[dict[str, Any], dict[str, tuple[dict[str, Any], bytes]]]:
    if not root.is_dir() or (root / MANIFEST).is_symlink():
        raise ValueError("package directory/manifest invalid")
    m = section((root / MANIFEST).read_bytes(), "PACKAGE_MANIFEST")
    if m.get("schema_version") != FORMAT or m.get("profile_id") != PROFILE:
        raise ValueError("format/profile mismatch")
    if m.get("authority_effect") != "NONE" or m.get("runtime_currentness") != "NOT_REVALIDATED":
        raise ValueError("packaging cannot promote runtime authority/currentness")
    root_keys = {"schema_version", "profile_id", "release_id", "release_date", "package_role",
                 "architecture_release_in_sources", "authority_effect", "runtime_currentness",
                 "attachment_limit", "reserved_slots", "attachment_files", "source_count",
                 "archives", "excluded_binary_cache", "sources", "carrier_specs",
                 "reconstruction_policy", "knowledge_integrity", "hosted_project_validation",
                 "self_hash_policy", "files", "source_vector_digest", "package_content_digest"}
    if set(m) != root_keys:
        raise ValueError("manifest fields must be exact")
    names = m.get("attachment_files")
    if type(names) is not list or len(names) != 32 or len(set(names)) != 32:
        raise ValueError("profile requires exactly 32 distinct attachments")
    if m.get("attachment_limit") != 40 or m.get("reserved_slots") != 8:
        raise ValueError("attachment budget mismatch")
    actual = sorted(p.name for p in root.iterdir())
    if actual != sorted(names):
        raise ValueError("missing or unexpected attachment")
    for name in names:
        p = safe_relative(name)
        if len(p.parts) != 1 or not name.endswith(".md"):
            raise ValueError("attachments must be flat Markdown files")
        f = root / name
        if f.is_symlink() or not f.is_file() or f.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("attachment type/size invalid")
        raw = f.read_bytes()
        raw.decode("utf-8", "strict")
        head = raw[:512]
        if (f"PROFILE_ID={PROFILE}\n".encode() not in head
                or f"RELEASE_ID={m['release_id']}\n".encode() not in head
                or b"PACKAGE_AUTHORITY=NONE\n" not in head):
            raise ValueError("mixed release/profile header")
    vector = file_vector(root)
    if vector != m.get("files"):
        raise ValueError("attachment SHA-256/length mismatch")
    if digest(b"LION/RAG-FILES/1\0" + canonical(vector)) != m.get("package_content_digest"):
        raise ValueError("package content digest mismatch")
    sources = m.get("sources")
    if type(sources) is not list or not sources:
        raise ValueError("source inventory missing")
    if type(m.get("source_count")) is not int or m["source_count"] != len(sources):
        raise ValueError("source cardinality mismatch")
    archive_ids = {a["archive_id"] for a in m["archives"]}
    if len(archive_ids) != len(m["archives"]):
        raise ValueError("duplicate archive identity")
    for a in m["archives"]:
        if not SHA.fullmatch(a["sha256"]):
            raise ValueError("archive digest invalid")
        represented = sum(s["archive_id"] == a["archive_id"] for s in sources)
        excluded = sum(e["archive_id"] == a["archive_id"] for e in m["excluded_binary_cache"])
        if represented + excluded != a["file_count"]:
            raise ValueError("archive member cardinality mismatch")
    for e in m["excluded_binary_cache"]:
        safe_relative(e["path"])
        if e["archive_id"] not in archive_ids or not e["path"].endswith(".pyc") or not SHA.fullmatch(e["sha256"]):
            raise ValueError("invalid excluded-cache record")
    allowed_classes = {"ORIGINAL_SOURCE_SNAPSHOT", "PRIOR_DERIVED_CANDIDATE"}
    ids, paths = set(), set()
    for s in sources:
        source_keys = {"source_id", "archive_id", "original_path", "virtual_path", "sha256", "bytes",
                       "carrier", "anchor", "source_class", "currentness", "authority_effect",
                       "content_interpretation", "declared_package_version", "declared_generated_at", "language"}
        if type(s) is not dict or set(s) != source_keys:
            raise ValueError("source fields must be exact")
        if s["source_id"] in ids or s["virtual_path"] in paths:
            raise ValueError("duplicate source identity/path")
        ids.add(s["source_id"]); paths.add(s["virtual_path"])
        safe_relative(s["original_path"]); safe_relative(s["virtual_path"])
        if s["archive_id"] not in archive_ids or s["virtual_path"] != s["archive_id"] + "/" + s["original_path"]:
            raise ValueError("source namespace mismatch")
        expected_id = "SRC-" + s["archive_id"].upper() + "-" + digest(s["original_path"].encode())[:12]
        if s["source_id"] != expected_id or s["anchor"] != expected_id.lower():
            raise ValueError("unstable source identity")
        if s["source_class"] not in allowed_classes or s["currentness"] != "NOT_REVALIDATED":
            raise ValueError("invalid source epistemic class")
        if s["authority_effect"] != "NONE" or s["content_interpretation"] != "DATA_NOT_EXECUTION_INSTRUCTIONS":
            raise ValueError("source data cannot grant authority")
        if not SHA.fullmatch(s["sha256"]) or type(s["bytes"]) is not int:
            raise ValueError("source digest/length invalid")
        if s["carrier"] not in names or not 8 <= int(s["carrier"][:2]) <= 31:
            raise ValueError("source carrier invalid")
    if source_digest(sources) != m.get("source_vector_digest"):
        raise ValueError("source vector digest mismatch")
    records = {}
    for name in names:
        if not 8 <= int(name[:2]) <= 31:
            continue
        for meta, body in parse_records((root / name).read_bytes()):
            sid = meta["source_id"]
            if sid in records or meta["carrier"] != name:
                raise ValueError("duplicate/misrouted record")
            records[sid] = (meta, body)
    if set(records) != ids:
        raise ValueError("source coverage mismatch")
    for s in sources:
        meta, body = records[s["source_id"]]
        if meta != s:
            raise ValueError("source metadata differs from manifest")
        if s["language"] == "json":
            load_json(body)
        elif s["language"] == "python":
            ast.parse(body.decode("utf-8"), filename=s["virtual_path"])
    # This validates the new continuation record, NOT any historical runtime schema.
    state = section((root / STATE).read_bytes(), "CONTINUATION_STATE")
    expected_state_keys = {"schema_version", "release_id", "runtime_currentness", "next_step", "effects", "last_reported_snapshot", "claim_groups", "required_read_sets"}
    if set(state) != expected_state_keys or state["schema_version"] != "lion.rag-continuation/v1":
        raise ValueError("continuation state schema invalid")
    if state["release_id"] != m["release_id"] or state["runtime_currentness"] != "NOT_REVALIDATED":
        raise ValueError("continuation cannot claim live currentness")
    if state["next_step"] != "REACQUIRE_SCOPE_BOUND_LIVE_STATE":
        raise ValueError("historical next step must not auto-run")
    if state["effects"] != {"repository": "NONE", "host": "NONE", "production": "NONE", "authority": "NONE"}:
        raise ValueError("continuation effect expansion")
    for group in state["claim_groups"]:
        if group["currentness"] != "NOT_REVALIDATED" or not group["source_ids"]:
            raise ValueError("claim group requires scoped source references")
        if not set(group["source_ids"]) <= ids:
            raise ValueError("claim source unresolved")
    for rs in state["required_read_sets"].values():
        if not set(rs) <= set(names):
            raise ValueError("required reading unresolved")
    tests = section((root / CASES).read_bytes(), "RETRIEVAL_CASES")
    caseids = set()
    for case in tests["cases"]:
        if case["id"] in caseids or not case["source_ids"]:
            raise ValueError("retrieval test invalid")
        caseids.add(case["id"])
        for sid in case["source_ids"]:
            if sid not in records:
                raise ValueError("retrieval source unresolved")
            if records[sid][0]["carrier"] not in case["carriers"]:
                raise ValueError("retrieval routing mismatch")
        if not set(case["carriers"]) <= set(names):
            raise ValueError("retrieval carrier unresolved")
    routing = (root / "02_ROUTING_AND_SOURCE_MAP.md").read_text("utf-8")
    for s in sources:
        if s["source_id"] not in routing or s["virtual_path"] not in routing:
            raise ValueError("source missing from visible routing index")
    return m, records

def result(root: Path) -> dict[str, Any]:
    m, records = verify(root)
    return {"status": "PASS", "release_id": m["release_id"], "attachments": len(m["attachment_files"]),
            "reserved_slots": m["reserved_slots"], "virtual_sources": len(records),
            "source_bytes": sum(len(body) for _, body in records.values()),
            "json_sources_parsed": sum(meta["language"] == "json" for meta, _ in records.values()),
            "python_sources_syntax_checked_not_executed": sum(meta["language"] == "python" for meta, _ in records.values()),
            "routing_cases_checked": len(section((root / CASES).read_bytes(), "RETRIEVAL_CASES")["cases"]),
            "package_content_digest": m["package_content_digest"], "runtime_currentness": "NOT_REVALIDATED",
            "project_indexing_and_retrieval": "NOT_RUN", "authority_effect": "NONE"}

def empty_destination(path: Path) -> None:
    if path.exists():
        raise ValueError("destination must not exist; refusing to overwrite")
    path.mkdir(parents=True)

def extract(root: Path, out: Path) -> dict[str, Any]:
    m, records = verify(root)
    empty_destination(out)
    for meta, body in records.values():
        target = out / "sources" / str(safe_relative(meta["virtual_path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    controls = {name: (root / name).read_text("utf-8") for name in m["attachment_files"]
                if int(name[:2]) < 8 and name != MANIFEST}
    recipe = {"schema_version": "lion.rag-rebuild/v1", "manifest": m, "controls": controls}
    (out / "bundle_recipe.json").write_bytes(json.dumps(recipe, ensure_ascii=False, indent=2).encode())
    return {"status": "PASS", "restored_text_sources": len(records), "destination": str(out),
            "cache_files_restored": 0, "source_code_executed": False}

def rebuild(recipe_path: Path, source_root: Path, out: Path) -> dict[str, Any]:
    recipe = load_json(recipe_path.read_bytes())
    if recipe.get("schema_version") != "lion.rag-rebuild/v1":
        raise ValueError("recipe schema mismatch")
    m = recipe["manifest"]
    # Validate output paths before making a new package; recipes are data.
    for name in list(recipe["controls"]) + [c["path"] for c in m["carrier_specs"]]:
        if len(safe_relative(name).parts) != 1 or not name.endswith(".md") or name not in m["attachment_files"]:
            raise ValueError("recipe output path invalid")
    # Verify all declared source identities before making a new package.
    payload = {}
    for s in m["sources"]:
        p = source_root / str(safe_relative(s["virtual_path"]))
        if p.is_symlink() or not p.resolve().is_relative_to(source_root.resolve()):
            raise ValueError("symlink/escaping source rejected")
        b = p.read_bytes()
        if digest(b) != s["sha256"] or len(b) != s["bytes"]:
            raise ValueError("source change requires an explicit new reviewed revision")
        payload[s["source_id"]] = b
    empty_destination(out)
    for name, text in recipe["controls"].items():
        if len(safe_relative(name).parts) != 1:
            raise ValueError("control path invalid")
        (out / name).write_bytes(text.encode("utf-8"))
    for spec in m["carrier_specs"]:
        raw = spec["prefix"].encode("utf-8")
        for s in m["sources"]:
            if s["carrier"] == spec["path"]:
                raw += render_record(s, payload[s["source_id"]])
        (out / spec["path"]).write_bytes(raw)
    seal(out, m)
    return result(out)

def compare_archive(root: Path, source_zip: Path, archive_id: str) -> dict[str, Any]:
    m, records = verify(root)
    info = next((a for a in m["archives"] if a["archive_id"] == archive_id), None)
    if info is None or digest(source_zip.read_bytes()) != info["sha256"]:
        raise ValueError("input archive SHA-256 mismatch")
    with zipfile.ZipFile(source_zip) as z:
        members = [i for i in z.infolist() if not i.is_dir()]
        seen = set(); count = 0
        for i in members:
            parts = PurePosixPath(i.filename).parts
            p = "/".join(parts[1:])
            safe_relative(p)
            if p in seen:
                raise ValueError("duplicate archive path")
            seen.add(p)
            candidates = [(meta, body) for meta, body in records.values()
                          if meta["archive_id"] == archive_id and meta["original_path"] == p]
            if candidates:
                if len(candidates) != 1 or candidates[0][1] != z.read(i):
                    raise ValueError("round-trip bytes differ from original")
                count += 1
            else:
                ex = [e for e in m["excluded_binary_cache"] if e["archive_id"] == archive_id and e["path"] == p]
                if len(ex) != 1 or digest(z.read(i)) != ex[0]["sha256"]:
                    raise ValueError("unrepresented original artifact")
        if count != sum(s["archive_id"] == archive_id for s in m["sources"]):
            raise ValueError("source archive coverage mismatch")
    return {"status": "PASS", "archive_id": archive_id, "archive_members": len(members),
            "text_sources_byte_identical": count, "binary_cache_recorded_outside_rag": len(members) - count}

def self_test(root: Path) -> dict[str, Any]:
    base, records = verify(root)
    checks = []
    def test(name, change, reseal=False):
        with tempfile.TemporaryDirectory(prefix="lion-rag-test-") as t:
            d = Path(t) / "p"; shutil.copytree(root, d)
            m = copy.deepcopy(base)
            change(d, m)
            if reseal:
                seal(d, m)
            try:
                verify(d)
            except (ValueError, KeyError, TypeError, FileNotFoundError, UnicodeDecodeError) as exc:
                checks.append({"test": name, "status": "PASS_REJECTED", "reason": str(exc)})
            else:
                raise AssertionError(f"negative test unexpectedly accepted: {name}")
    first = base["carrier_specs"][0]["path"]
    test("missing_carrier", lambda d, m: (d / first).unlink())
    test("payload_corruption", lambda d, m: (d / first).write_bytes((d / first).read_bytes() + b"x"))
    test("unexpected_33rd_file", lambda d, m: (d / "UNREGISTERED.md").write_text("x"))
    test("mixed_epoch_header", lambda d, m: (d / first).write_bytes((d / first).read_bytes().replace(m["release_id"].encode(), b"OTHER_EPOCH", 1)), True)
    test("authority_promotion", lambda d, m: m.update(authority_effect="WRITE"), True)
    test("unobserved_currentness_promotion", lambda d, m: m.update(runtime_currentness="CURRENT"), True)
    test("source_omitted_from_map", lambda d, m: m["sources"].pop(), True)
    test("duplicate_source_id", lambda d, m: m["sources"].append(copy.deepcopy(m["sources"][0])), True)
    test("source_path_traversal", lambda d, m: m["sources"][0].update(original_path="../outside"), True)
    test("source_misrouting", lambda d, m: m["sources"][0].update(carrier=base["carrier_specs"][-1]["path"]), True)
    test("source_authority_from_document", lambda d, m: m["sources"][0].update(authority_effect="GRANT"), True)
    test("invalid_source_class", lambda d, m: m["sources"][0].update(source_class="LIVE_TRUTH"), True)
    test("unknown_budget", lambda d, m: m.update(attachment_limit=41), True)
    test("false_source_count", lambda d, m: m.update(source_count=1), True)
    test("unknown_manifest_field", lambda d, m: m.update(undeclared_override=True), True)
    test("unknown_source_metadata_field", lambda d, m: m["sources"][0].update(undeclared_override=True), True)
    def corrupt_frame(d, m):
        name = m["sources"][0]["carrier"]
        raw = (d / name).read_bytes()
        (d / name).write_bytes(raw.replace(b"LION_RECORD_END: ", b"LION_RECORD_BAD: ", 1))
    test("frame_corruption_even_when_carrier_rehashed", corrupt_frame, True)
    with tempfile.TemporaryDirectory(prefix="lion-rag-roundtrip-") as t:
        e, p = Path(t) / "extracted", Path(t) / "rebuilt"
        extract(root, e)
        rebuild(e / "bundle_recipe.json", e / "sources", p)
        if any((root / n).read_bytes() != (p / n).read_bytes() for n in base["attachment_files"]):
            raise AssertionError("deterministic package round-trip mismatch")
        checks.append({"test": "extract_rebuild_32_files_byte_identical", "status": "PASS"})
    return {"status": "PASS", "tests": checks, "test_count": len(checks), "scope": "OFFLINE_CONTAINER_NOT_LIVE_RUNTIME_OR_HOSTED_RAG"}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("verify", "self-test", "locate", "extract", "compare"):
        s = sub.add_parser(cmd); s.add_argument("package", type=Path)
        if cmd == "extract": s.add_argument("destination", type=Path)
        if cmd == "compare":
            s.add_argument("source_zip", type=Path); s.add_argument("archive_id")
        if cmd == "locate": s.add_argument("query")
    s = sub.add_parser("rebuild")
    s.add_argument("recipe", type=Path); s.add_argument("sources", type=Path); s.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify": out = result(args.package)
        elif args.command == "self-test": out = self_test(args.package)
        elif args.command == "extract": out = extract(args.package, args.destination)
        elif args.command == "compare": out = compare_archive(args.package, args.source_zip, args.archive_id)
        elif args.command == "rebuild": out = rebuild(args.recipe, args.sources, args.destination)
        else:
            m, _ = verify(args.package)
            q = args.query.casefold()
            out = [{k: s[k] for k in ("source_id", "virtual_path", "carrier", "sha256", "source_class", "currentness")}
                   for s in m["sources"] if q in s["virtual_path"].casefold() or q in s["source_id"].casefold()]
        print(json.dumps(out, ensure_ascii=False, indent=2)); return 0
    except (ValueError, KeyError, TypeError, OSError, SyntaxError, AssertionError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

````
