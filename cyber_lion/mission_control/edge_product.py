"""Portable product CLI: byte-integrity check, not authorship or correctness proof."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import re
import stat
import sys
MAX_BYTES = 131072

def verify_tree(root, manifest):
    root = Path(root).absolute()
    if root != root.resolve() or root.is_symlink() or not root.is_dir():
        raise ValueError('root')
    if type(manifest) is not dict or set(manifest) != {'schema','files'} or manifest['schema'] != 'lion.simple-product/v1':
        raise ValueError('manifest schema')
    rows = manifest['files']
    if type(rows) is not list or not 1 <= len(rows) <= 64:
        raise ValueError('file count')
    expected, seen = {}, set()
    for row in rows:
        if type(row) is not dict or set(row) != {'path','size','sha256'}:
            raise ValueError('file fields')
        name = row['path']
        if type(name) is not str or len(name) > 160:
            raise ValueError('path')
        for part in name.split('/'):
            if (re.fullmatch('[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}', part) is None or part.endswith('.')
                    or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(10)),*(f'LPT{i}' for i in range(10))}):
                raise ValueError('path')
        if name.casefold() in seen:
            raise ValueError('case collision')
        seen.add(name.casefold())
        if type(row['size']) is not int or not 0 <= row['size'] <= MAX_BYTES:
            raise ValueError('size')
        if type(row['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None:
            raise ValueError('digest')
        expected[name] = row
    observed = set()
    for p in root.rglob('*'):
        st = p.lstat()
        if p.is_symlink() or getattr(st,'st_file_attributes',0) & 0x400:
            raise ValueError('link/reparse')
        if stat.S_ISDIR(st.st_mode):
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES or st.st_nlink != 1:
            raise ValueError('regular file')
        name = p.relative_to(root).as_posix()
        if name not in expected:
            raise ValueError('extra file')
        with p.open('rb') as stream:
            data = stream.read(MAX_BYTES+1)
        if len(data) != expected[name]['size'] or sha256(data).hexdigest() != expected[name]['sha256']:
            raise ValueError('content')
        observed.add(name)
    if observed != set(expected):
        raise ValueError('missing file')
    return dict(status='PASS', file_count=len(observed), authority_effect='NONE')

def main():
    def unique(items):
        v = {}
        for k,x in items:
            if k in v:
                raise ValueError('duplicate JSON key')
            v[k] = x
        return v
    try:
        if len(sys.argv) != 3:
            raise ValueError('usage: product_verifier.py ROOT MANIFEST.json')
        with Path(sys.argv[2]).open('rb') as f:
            raw = f.read(65537)
        if len(raw) > 65536:
            raise ValueError('manifest limit')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
        print(json.dumps(verify_tree(sys.argv[1], value)))
        return 0
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(status='REJECTED',error=str(exc))))
        return 2
if __name__ == '__main__':
    raise SystemExit(main())
