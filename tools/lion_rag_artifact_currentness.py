"""Read-only currentness classifier for material RAG32 artifact bytes.

Validation proves package structure and bytes. Currentness requires an explicit
trusted expectation (release + manifest SHA256). Historical reports or a release
name alone never promote an artifact to current exact evidence.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,tempfile,shutil
from pathlib import Path
try:
    from tools.lion_rag32_validate import validate,RagValidationError
except ModuleNotFoundError:  # direct: python tools/lion_rag_artifact_currentness.py
    from lion_rag32_validate import validate,RagValidationError
DOMAIN=b"LION/RAG32/ARTIFACT-CURRENTNESS/1\0"

def _canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


def _git(repository:Path,*args:str)->subprocess.CompletedProcess:
    return subprocess.run(['git','-c',f'safe.directory={repository}',*args],cwd=repository,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)

def _exact_git_artifact_view(repo:Path,root:Path):
    """Return a temporary exact-HEAD view for a tracked repository artifact.

    Windows checkout line-ending materialization is not repository object identity.
    If the artifact is fully represented in HEAD, currentness/manifest binding uses
    exact Git blob bytes. Untracked candidates intentionally fall back to supplied bytes.
    """
    try: rel=root.relative_to(repo).as_posix()
    except ValueError:return None
    probe=_git(repo,'ls-tree','-r','--name-only','HEAD','--',rel)
    if probe.returncode!=0:return None
    paths=[x.decode('utf-8') for x in probe.stdout.splitlines() if x]
    md=[x for x in paths if x.endswith('.md') and Path(x).parent.as_posix()==rel]
    if not md:return None
    working={p.name for p in root.glob('*.md')}
    tracked={Path(x).name for x in md}
    if working!=tracked:return None
    td=tempfile.TemporaryDirectory(prefix='.rag-currentness-',dir=str((repo/'LION/rag').resolve()))
    view=Path(td.name)
    try:
        for gitpath in md:
            cp=_git(repo,'show','HEAD:'+gitpath)
            if cp.returncode!=0:raise RuntimeError('git blob read failed: '+gitpath)
            (view/Path(gitpath).name).write_bytes(cp.stdout)
    except Exception:
        td.cleanup();raise
    head=_git(repo,'rev-parse','HEAD').stdout.decode().strip()
    return td,view,head

def _fileset_digest(root:Path):
    rows=[]
    for p in sorted(root.glob('*.md')):
        b=p.read_bytes();rows.append({'name':p.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    return hashlib.sha256(DOMAIN+_canon(rows)).hexdigest(),rows

def classify(repository,artifact_root,*,expected_release=None,expected_manifest_sha256=None):
    repo=Path(repository).resolve();root=Path(artifact_root).resolve()
    if not root.is_dir():
        return {'status':'UNKNOWN_MISSING','currentness':'UNKNOWN','artifact_root':str(root),'authority_effect':'NONE','runtime_effect':'NONE'}
    exact=None;validation_root=root;byte_source='SUPPLIED_BYTES';source_head=None
    try:
        exact=_exact_git_artifact_view(repo,root)
        if exact is not None:
            _td,validation_root,source_head=exact;byte_source='EXACT_GIT_HEAD_BLOBS'
        # Validator is repository-local by design. A temporary exact-Git view under
        # repo/LION/rag is legal; external candidates use bounded external validation.
        if validation_root.is_relative_to((repo/'LION/rag').resolve()):
            result=validate(repo,str(validation_root.relative_to(repo)))
        else:
            try:
                from tools.lion_rag32_validate import _records,MANIFEST
            except ModuleNotFoundError:
                from lion_rag32_validate import _records,MANIFEST
            files=sorted(validation_root.glob('*.md'))
            if not 1 <= len(files) <= 40:raise RagValidationError('attachment budget exceeded')
            mt=(validation_root/'05_PACKAGE_MANIFEST.md').read_text(encoding='utf-8');m=MANIFEST.search(mt)
            if not m:raise RagValidationError('manifest unavailable')
            manifest=json.loads(m.group(1));profile=manifest.get('profile_id');release=manifest.get('release_id')
            if profile!='LION-RAG32/1' or not isinstance(release,str) or not release:raise RagValidationError('profile/release')
            expected=manifest.get('attachment_files')
            if not isinstance(expected,list) or sorted(expected)!=sorted(p.name for p in files):raise RagValidationError('manifest fileset')
            if manifest.get('attachment_limit')!=40:raise RagValidationError('attachment limit')
            if manifest.get('reserved_slots')!=40-len(files):raise RagValidationError('reserved slot budget')
            for p in files:
                head=p.read_text(encoding='utf-8').split('LION_RECORD_BEGIN',1)[0]
                if f'PROFILE_ID={profile}' not in head or f'RELEASE_ID={release}' not in head:raise RagValidationError('mixed release: '+p.name)
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
            result={'status':'PASS','profile_id':profile,'release_id':release,'file_count':len(files),'source_count':len(records),'manifest_sha256':hashlib.sha256((validation_root/'05_PACKAGE_MANIFEST.md').read_bytes()).hexdigest(),'authority_effect':'NONE'}
        digest,rows=_fileset_digest(validation_root)
        release=result['release_id'];manifest_sha=result['manifest_sha256']
        if expected_release is None or expected_manifest_sha256 is None:
            currentness='VALIDATED_UNBOUND'
        elif release!=expected_release:
            currentness='STALE_RELEASE'
        elif manifest_sha!=expected_manifest_sha256:
            currentness='UNKNOWN_MANIFEST_MISMATCH'
        else:
            currentness='EXACT_BOUND_CURRENT'
        return {**result,'currentness':currentness,'artifact_root':str(root),'artifact_fileset_digest':digest,'artifact_file_count':len(rows),'artifact_byte_source':byte_source,'source_head':source_head,'expected_release':expected_release,'expected_manifest_sha256':expected_manifest_sha256,'runtime_effect':'NONE'}
    except (RagValidationError,FileNotFoundError,ValueError,json.JSONDecodeError,RuntimeError) as exc:
        return {'status':'INVALID','currentness':'UNKNOWN','error':str(exc),'artifact_root':str(root),'artifact_byte_source':byte_source,'authority_effect':'NONE','runtime_effect':'NONE'}
    finally:
        if exact is not None:exact[0].cleanup()

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--repository',default='.');ap.add_argument('--artifact-root',required=True);ap.add_argument('--expected-release');ap.add_argument('--expected-manifest-sha256');a=ap.parse_args(argv)
    v=classify(a.repository,a.artifact_root,expected_release=a.expected_release,expected_manifest_sha256=a.expected_manifest_sha256);print(json.dumps(v,sort_keys=True,separators=(',',':')));raise SystemExit(0 if v.get('currentness')=='EXACT_BOUND_CURRENT' else 2)
if __name__=='__main__':main()
