"""Read-only validator for repository-local LION RAG32 package candidates.

Record parsing is length-delimited by LION_RECORD_META.bytes. Marker-looking text
inside payload bytes is therefore data and cannot create a synthetic record.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

BEGIN=re.compile(br"(?m)^LION_RECORD_BEGIN: ([^\n]+)\n")
MANIFEST=re.compile(r"LION_DATA_BEGIN: PACKAGE_MANIFEST\n```json\n(.*?)\n```",re.S)

class RagValidationError(ValueError):pass

def _records(raw):
    cursor=0
    while True:
        match=BEGIN.search(raw,cursor)
        if match is None:return
        rid=match.group(1).decode("utf-8","strict").strip()
        pos=match.end(); prefix=b"LION_RECORD_META: "
        if not raw.startswith(prefix,pos):raise RagValidationError("record metadata missing: "+rid)
        meta_end=raw.find(b"\n",pos)
        if meta_end<0:raise RagValidationError("record metadata line: "+rid)
        try:meta=json.loads(raw[pos+len(prefix):meta_end].decode("utf-8","strict"))
        except (UnicodeError,ValueError) as exc:raise RagValidationError("record metadata JSON: "+rid) from exc
        size=meta.get("bytes")
        if type(size) is not int or size<0:raise RagValidationError("record bytes: "+rid)
        fence_start=meta_end+1; fence_end=raw.find(b"\n",fence_start)
        if fence_end<0 or not raw[fence_start:fence_end].startswith(b"````"):raise RagValidationError("record opening fence: "+rid)
        payload_start=fence_end+1; payload_end=payload_start+size
        if payload_end>len(raw):raise RagValidationError("record payload truncated: "+rid)
        payload=raw[payload_start:payload_end]
        close=b"\n````\nLION_RECORD_END: "+rid.encode("utf-8")
        if not raw.startswith(close,payload_end):raise RagValidationError("record closing frame: "+rid)
        end=payload_end+len(close)
        if end<len(raw) and raw[end:end+1]==b"\n":end+=1
        yield rid,meta,payload,raw[match.start():end]
        cursor=end

def validate(repository,rag_root):
    repo=Path(repository).resolve(strict=True); root=(repo/rag_root).resolve(strict=True)
    rag_base=(repo/"LION"/"rag").resolve(strict=True)
    if not root.is_relative_to(rag_base):raise RagValidationError("RAG root outside LION/rag")
    files=sorted(root.glob("*.md"))
    if len(files)!=32:raise RagValidationError("exact 32 markdown containers required")
    mt=(root/"05_PACKAGE_MANIFEST.md").read_text(encoding="utf-8"); mm=MANIFEST.search(mt)
    if not mm:raise RagValidationError("manifest unavailable")
    manifest=json.loads(mm.group(1)); profile=manifest.get("profile_id"); release=manifest.get("release_id")
    if profile!="LION-RAG32/1" or type(release) is not str or not release:raise RagValidationError("profile/release")
    expected=manifest.get("attachment_files")
    if type(expected) is not list or sorted(expected)!=sorted(p.name for p in files):raise RagValidationError("manifest fileset")
    for p in files:
        head=p.read_text(encoding="utf-8").split("LION_RECORD_BEGIN",1)[0]
        if f"PROFILE_ID={profile}" not in head or f"RELEASE_ID={release}" not in head:raise RagValidationError("mixed release: "+p.name)
    file_hashes=manifest.get("file_sha256_excluding_manifest") or manifest.get("file_sha256") or manifest.get("attachment_sha256")
    if type(file_hashes) is dict:
        for name,pin in file_hashes.items():
            if name=="05_PACKAGE_MANIFEST.md":continue
            path=root/name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=pin:raise RagValidationError("file digest: "+name)
    records={}; paths=set()
    for p in files:
        for rid,meta,payload,block in _records(p.read_bytes()):
            if rid in records:raise RagValidationError("duplicate source id")
            if meta.get("source_id")!=rid:raise RagValidationError("source id substitution")
            vp=meta.get("virtual_path")
            if type(vp) is not str or not vp or vp in paths:raise RagValidationError("virtual path collision")
            paths.add(vp)
            if len(payload)!=meta.get("bytes") or hashlib.sha256(payload).hexdigest()!=meta.get("sha256"):raise RagValidationError("payload bytes/hash: "+rid)
            records[rid]=(p.name,meta)
    if len(records)!=manifest.get("source_count"):raise RagValidationError(f"source count: observed={len(records)} expected={manifest.get('source_count')}")
    if "predecessor_record_count" in manifest and manifest["predecessor_record_count"]>len(records):raise RagValidationError("predecessor count")
    return {"status":"PASS","profile_id":profile,"release_id":release,"file_count":len(files),"source_count":len(records),"manifest_sha256":hashlib.sha256((root/"05_PACKAGE_MANIFEST.md").read_bytes()).hexdigest(),"authority_effect":"NONE"}

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument("--repository",default="."); ap.add_argument("--root",required=True); args=ap.parse_args(argv)
    print(json.dumps(validate(args.repository,args.root),sort_keys=True,separators=(",",":")))
if __name__=="__main__":main()
