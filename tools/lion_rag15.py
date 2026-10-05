#!/usr/bin/env python3
"""Verify, route and package the explicit 30-file LION knowledge release.

Standard library only; no model calls, network access, repository writes or
runtime effects. `pack` writes only the explicitly selected output archive.
The history index contains references, not the original R9 payload bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

RELEASE = 'lion-rag30-v1.5-r1'
MANIFEST = '29_PACKAGE_MANIFEST.json'
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / 'LION/rag/lion_project_rag30_v1_5_r1'
REPOS = {'ai_platform','swarm','chunk-chunk','glitchlab','HA2D',
         'hipotezy_nadawcze_LLM','mosaic_lab_pro.py','sbom',
         'SymulacjaKaskadySieciowej','writeups'}
# These are transparent topic rules, not a semantic model or a live registry.
RULES = (
    (('semantic','semant','missionintent','queryplan','scaffold','relevance'), ('06','07'), ()),
    (('saas','local','lokaln','provider'), ('08','09'), ()),
    (('conversation','binding_epoch','lost response','odpowiedz'), ('08','09','16'), ()),
    (('lpcl','panel','compile_canonical_run'), ('10','21'), ()),
    (('gap','capabilityneed','bean','generatyw','mosaic'), ('11','20','21'), ()),
    (('swarm','docker','workload'), ('12','14'), ('swarm',)),
    (('aid','sbom','pochodzenie','provenance'), ('12','13','14'), ('sbom',)),
    (('ha2d','snapshot','replay','pamiec'), ('13','14','16'), ('HA2D',)),
    (('glitchlab','delta','invariants'), ('06','14','17'), ('glitchlab',)),
    (('mosaic_lab_pro','headless graph'), ('06','07','14'), ('mosaic_lab_pro.py',)),
    (('chunk-chunk','hmk9d','hmk-9d'), ('06','10','14'), ('chunk-chunk',)),
    (('hipotezy_nadawcze','eksperyment','falsyfikator'), ('14','17'), ('hipotezy_nadawcze_LLM',)),
    (('symulacjakaskadysieciowej','simulationresult','modelriskstatement'), ('13','14','17'), ('SymulacjaKaskadySieciowej',)),
    (('writeups','retention','badania'), ('13','14','17','18'), ('writeups',)),
    (('pdp','allow','admission','authority'), ('12','16'), ()),
    (('ewoluc','evolution','federac','metaprompt','program misji'), ('05','14','15','20','21','22','23'), ()),
    (('history','historycz','r9','source_id','supersession'), ('18','24'), ()),
    (('windows','cp1252','unicodeencodeerror','utf-8'), ('19',), ()),
)

class PackageError(ValueError):
    """The requested release or input failed a closed offline check."""


def configure_utf8() -> None:
    # -I ignores PYTHON* environment variables. Fix the actual stream, not env.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            reconfigure(encoding='utf-8', errors='strict')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise PackageError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(PackageError('non-finite JSON: '+value)))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_digest(file_hashes: dict[str, str]) -> str:
    return sha(b'LION/RAG30/CONTENT/1\0' + json.dumps(file_hashes, sort_keys=True,
               separators=(',', ':'), ensure_ascii=False).encode('utf-8'))


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    paths = list(root.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise PackageError('release must be flat regular files without symlinks')
    if len(paths) != 30:
        raise PackageError('expected exactly 30 release files')
    manifest = read_json(root / MANIFEST)
    keys = {'schema','release_id','version','file_count','upload_limit','status',
            'canonical_owner','source_cutoff','source_state','authority_effect',
            'runtime_effect','historical_payloads_embedded','files','content_digest',
            'self_hash_policy','entrypoints','versioning_note','publication_note'}
    if not isinstance(manifest, dict) or set(manifest) != keys:
        raise PackageError('manifest fields mismatch')
    if manifest['schema'] != 'analysis.rag30-release/v1' or manifest['release_id'] != RELEASE:
        raise PackageError('wrong knowledge release')
    if type(manifest['file_count']) is not int or type(manifest['upload_limit']) is not int or manifest['file_count'] != 30 or manifest['upload_limit'] != 30:
        raise PackageError('wrong release file bound')
    if manifest['version'] != '1.5.0' or manifest['status'] != 'READY_FOR_PROJECT_KNOWLEDGE_USE':
        raise PackageError('wrong release version/status')
    if manifest['canonical_owner'] != 'DonkeyJJLove/ai_platform:LION/rag/RAG_BOOTSTRAP.json':
        raise PackageError('wrong canonical RAG owner')
    if manifest['authority_effect'] != 'NONE' or manifest['runtime_effect'] != 'NONE':
        raise PackageError('knowledge cannot grant authority or claim runtime effect')
    if manifest['historical_payloads_embedded'] is not False:
        raise PackageError('history index must not claim embedded original payloads')
    rows = manifest['files']
    if not isinstance(rows, dict) or set(rows) != {p.name for p in paths} - {MANIFEST}:
        raise PackageError('exact release file set mismatch')
    digests = {}
    for name, row in rows.items():
        if Path(name).name != name or '\\' in name or not re.fullmatch(r'\d{2}_[A-Z0-9_]+\.(md|json)', name):
            raise PackageError('invalid release filename')
        if set(row) != {'sha256','bytes'}:
            raise PackageError('manifest file record shape')
        data = (root/name).read_bytes()
        data.decode('utf-8', errors='strict')
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise PackageError('file integrity mismatch: '+name)
        if name.endswith('.json'):
            read_json(root/name)
        digests[name] = sha(data)
    if content_digest(digests) != manifest['content_digest']:
        raise PackageError('content digest mismatch')
    index = read_json(root/'24_SOURCE_RECORD_INDEX.json')
    columns = ['source_id','archive_id','virtual_path','carrier_key','payload_sha256','payload_bytes']
    if index.get('columns') != columns or index.get('payloads_embedded') is not False:
        raise PackageError('history index semantics mismatch')
    if index.get('record_count') != 211 or len(index.get('records', [])) != 211:
        raise PackageError('history index count mismatch')
    ids = set()
    for row in index['records']:
        if not isinstance(row,list) or len(row) != 6 or row[0] in ids:
            raise PackageError('duplicate or invalid history record')
        if row[3] not in index['carriers'] or not re.fullmatch(r'[0-9a-f]{64}',row[4]):
            raise PackageError('history location/digest mismatch')
        if type(row[5]) is not int or row[5] < 0:
            raise PackageError('history payload size invalid')
        ids.add(row[0])
    owners = read_json(root/'25_SEMANTIC_OWNERS.json')['owners']
    if len(owners) != 47 or len({r['concept'] for r in owners}) != len(owners):
        raise PackageError('semantic owner map mismatch')
    vector = read_json(root/'26_FEDERATION_SOURCE_VECTOR.json')
    records = vector['repositories']
    if len(records) != 10 or {r['repository'] for r in records} != {'DonkeyJJLove/'+r for r in REPOS}:
        raise PackageError('federation vector mismatch')
    if vector['deployment_vector'] is not False or vector['atomic'] is not False:
        raise PackageError('source vector misrepresented')
    for row in records:
        if not all(re.fullmatch(r'[0-9a-f]{40}', row.get(k,'')) for k in ('head','tree')):
            raise PackageError('invalid source Git identity')
    for p in paths:
        if p.suffix == '.md':
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):
                    continue
                rel = target.split('#',1)[0]
                candidate = (root/rel).resolve()
                if not candidate.is_relative_to(root) or not candidate.is_file():
                    raise PackageError('broken local Markdown link: '+rel)
    return {'result':'PASS','release_id':RELEASE,'files':30,'historical_record_references':211,
            'historical_payloads_embedded':False,'semantic_owners':47,'repositories':10,
            'content_digest':manifest['content_digest'],'verification_class':'BYTE_INTEGRITY_AND_STRUCTURE_NOT_AUTHENTICITY',
            'authority_effect':'NONE','runtime_effect':'NONE'}


def normalize(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c)).replace('ł','l')


def route(root: Path, query: str) -> dict:
    if not isinstance(query,str) or not query.strip() or len(query)>16000:
        raise PackageError('query must contain 1..16000 characters')
    verify(root)
    q = normalize(query)
    prefixes = {'00','01','02','03'}
    repos = {'ai_platform'}
    matches = []
    for triggers, files, peers in RULES:
        hit = [t for t in triggers if normalize(t) in q]
        if hit:
            prefixes.update(files); repos.update(peers); matches.extend(hit)
    selected = sorted(p.name for p in root.iterdir() if p.name[:2] in prefixes)
    return {'schema':'analysis.rag15-orientation/v1','release_id':RELEASE,'query':query,
            'mode':'DETERMINISTIC_TOPIC_ROUTING_NOT_MODEL_SEMANTIC_RETRIEVAL',
            'read_first':['00_START_HERE.md','01_MODEL_INSTRUCTIONS.md','03_STATE_AND_CONTINUATION.md','02_ROUTING_AND_SOURCE_MAP.md'],
            'selected_files':selected,'matched_terms':sorted(set(matches)),
            'repositories':sorted('DonkeyJJLove/'+r for r in repos),
            'next_source_read':'Read current ai_platform/AGENTS.md, canonical bootstrap, full documentation worklist and dependent peer source/tests.',
            'canonical_preferred_release_live':'REACQUIRE_NOT_ASSUMED_FROM_THIS_PACKAGE',
            'full_documentation_read_completed':False,'model_inference':'NOT_RUN',
            'authority_effect':'NONE','runtime_effect':'NONE'}


def lookup(root: Path, source_id: str) -> dict:
    verify(root)
    index = read_json(root/'24_SOURCE_RECORD_INDEX.json')
    row = next((r for r in index['records'] if r[0] == source_id), None)
    if row is None:
        raise PackageError('unknown historical source_id')
    result = dict(zip(index['columns'],row))
    result.update(physical_carrier=index['carriers'][row[3]],
                  base_archive_sha256=index['base_archive_sha256'],
                  payload_available_in_package=False, currentness='HISTORICAL_NOT_REACQUIRED',
                  authority_effect='NONE', next_step='Recover exact original bytes before dependent historical claim.')
    return result


def pack(root: Path, output: Path) -> dict:
    report = verify(root)
    if output.resolve().is_relative_to(root.resolve()):
        raise PackageError('output archive must be outside the 30-file release directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in sorted(root.iterdir()):
            info = zipfile.ZipInfo(p.name,(2026,10,4,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return {**report,'archive':str(output),'archive_sha256':sha(output.read_bytes()),
            'archive_bytes':output.stat().st_size}


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    commands = parser.add_subparsers(dest='command',required=True)
    commands.add_parser('verify')
    q=commands.add_parser('query'); q.add_argument('text')
    s=commands.add_parser('record'); s.add_argument('source_id')
    p=commands.add_parser('pack'); p.add_argument('output',type=Path)
    args = parser.parse_args()
    try:
        if args.command=='verify': result=verify(args.root)
        elif args.command=='query': result=route(args.root,args.text)
        elif args.command=='record': result=lookup(args.root,args.source_id)
        else: result=pack(args.root,args.output)
    except (PackageError,OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'result':'FAIL','error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
