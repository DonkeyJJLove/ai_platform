"""Read-only currentness classifier for material RAG32 artifact bytes.

Validation proves package structure and bytes. Currentness requires an explicit
trusted expectation (release + manifest SHA256). Historical reports or a release
name alone never promote an artifact to current exact evidence.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
try:
    from tools.lion_rag32_validate import validate,RagValidationError
except ModuleNotFoundError:  # direct: python tools/lion_rag_artifact_currentness.py
    from lion_rag32_validate import validate,RagValidationError
DOMAIN=b"LION/RAG32/ARTIFACT-CURRENTNESS/1\0"

def _canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def _fileset_digest(root:Path):
    rows=[]
    for p in sorted(root.glob('*.md')):
        b=p.read_bytes();rows.append({'name':p.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    return hashlib.sha256(DOMAIN+_canon(rows)).hexdigest(),rows

def classify(repository,artifact_root,*,expected_release=None,expected_manifest_sha256=None):
    repo=Path(repository).resolve();root=Path(artifact_root).resolve()
    if not root.is_dir():
        return {'status':'UNKNOWN_MISSING','currentness':'UNKNOWN','artifact_root':str(root),'authority_effect':'NONE','runtime_effect':'NONE'}
    # Validator is repository-local by design. For external material bytes, create a
    # logical path only if artifact is under repo/LION/rag; otherwise validate an exact
    # temporary repository view without mutating source bytes.
    try:
        if root.is_relative_to((repo/'LION/rag').resolve()):
            result=validate(repo,str(root.relative_to(repo)))
        else:
            # external validation mirrors the same invariants by copying no bytes: parse
            # through a temporary symlink-free view is deliberately avoided; external
            # candidates must provide exactly 32 markdown files and a parseable manifest.
            try:
                from tools.lion_rag32_validate import _records,MANIFEST
            except ModuleNotFoundError:
                from lion_rag32_validate import _records,MANIFEST
            files=sorted(root.glob('*.md'))
            if len(files)!=32:raise RagValidationError('exact 32 markdown containers required')
            mt=(root/'05_PACKAGE_MANIFEST.md').read_text(encoding='utf-8');m=MANIFEST.search(mt)
            if not m:raise RagValidationError('manifest unavailable')
            manifest=json.loads(m.group(1));profile=manifest.get('profile_id');release=manifest.get('release_id')
            if profile!='LION-RAG32/1' or not isinstance(release,str) or not release:raise RagValidationError('profile/release')
            expected=manifest.get('attachment_files')
            if not isinstance(expected,list) or sorted(expected)!=sorted(p.name for p in files):raise RagValidationError('manifest fileset')
            for p in files:
                head=p.read_text(encoding='utf-8').split('LION_RECORD_BEGIN',1)[0]
                if f'PROFILE_ID={profile}' not in head or f'RELEASE_ID={release}' not in head:raise RagValidationError('mixed release: '+p.name)
            file_hashes=manifest.get('file_sha256_excluding_manifest') or manifest.get('file_sha256') or manifest.get('attachment_sha256')
            if isinstance(file_hashes,dict):
                for name,pin in file_hashes.items():
                    if name=='05_PACKAGE_MANIFEST.md':continue
                    path=root/name
                    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=pin:raise RagValidationError('file digest: '+name)
            records={};paths=set()
            for p in files:
                for rid,meta,payload,block in _records(p.read_bytes()):
                    if rid in records:raise RagValidationError('duplicate source id')
                    if meta.get('source_id')!=rid:raise RagValidationError('source id substitution')
                    vp=meta.get('virtual_path')
                    if not isinstance(vp,str) or not vp or vp in paths:raise RagValidationError('virtual path collision')
                    paths.add(vp)
                    if len(payload)!=meta.get('bytes') or hashlib.sha256(payload).hexdigest()!=meta.get('sha256'):raise RagValidationError('payload bytes/hash: '+rid)
                    records[rid]=1
            if len(records)!=manifest.get('source_count'):raise RagValidationError('source count')
            result={'status':'PASS','profile_id':profile,'release_id':release,'file_count':len(files),'source_count':len(records),'manifest_sha256':hashlib.sha256((root/'05_PACKAGE_MANIFEST.md').read_bytes()).hexdigest(),'authority_effect':'NONE'}
    except (RagValidationError,FileNotFoundError,ValueError,json.JSONDecodeError) as exc:
        return {'status':'INVALID','currentness':'UNKNOWN','error':str(exc),'artifact_root':str(root),'authority_effect':'NONE','runtime_effect':'NONE'}
    digest,rows=_fileset_digest(root)
    release=result['release_id'];manifest_sha=result['manifest_sha256']
    if expected_release is None or expected_manifest_sha256 is None:
        currentness='VALIDATED_UNBOUND'
    elif release!=expected_release:
        currentness='STALE_RELEASE'
    elif manifest_sha!=expected_manifest_sha256:
        currentness='UNKNOWN_MANIFEST_MISMATCH'
    else:
        currentness='EXACT_BOUND_CURRENT'
    return {**result,'currentness':currentness,'artifact_root':str(root),'artifact_fileset_digest':digest,'artifact_file_count':len(rows),'expected_release':expected_release,'expected_manifest_sha256':expected_manifest_sha256,'runtime_effect':'NONE'}

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--repository',default='.');ap.add_argument('--artifact-root',required=True);ap.add_argument('--expected-release');ap.add_argument('--expected-manifest-sha256');a=ap.parse_args(argv)
    v=classify(a.repository,a.artifact_root,expected_release=a.expected_release,expected_manifest_sha256=a.expected_manifest_sha256);print(json.dumps(v,sort_keys=True,separators=(',',':')));raise SystemExit(0 if v.get('currentness')=='EXACT_BOUND_CURRENT' else 2)
if __name__=='__main__':main()
