"""Bounded bytes and local I/O for the edge-yoke extension; never authority."""
from __future__ import annotations
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import stat
import tempfile
import time

class EdgeRejected(ValueError):
    pass

def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')

def digest(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise EdgeRejected('exact bytes required')
    return sha256(raw).hexdigest()

def object_bytes(raw: bytes, limit: int = 1000000) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise EdgeRejected('duplicate JSON key')
            result[key] = value
        return result
    if type(raw) is not bytes or not 1 <= len(raw) <= limit:
        raise EdgeRejected('JSON byte limit')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(EdgeRejected('nonfinite JSON')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EdgeRejected('invalid UTF-8 JSON') from exc
    if type(value) is not dict:
        raise EdgeRejected('JSON object required')
    return value

def read_regular(path: str | Path, limit: int = 1000000) -> bytes:
    p = Path(path)
    st = p.lstat()
    if not stat.S_ISREG(st.st_mode) or getattr(st, 'st_file_attributes', 0) & 0x400:
        raise EdgeRejected('regular non-reparse file required')
    with p.open('rb') as stream:
        observed = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        final = os.fstat(stream.fileno())
    def identity(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns
    if len(raw) > limit or len(raw) != st.st_size or identity(st) != identity(observed) or identity(st) != identity(final):
        raise EdgeRejected('file changed or byte limit exceeded')
    return raw

def private_directory(path: str | Path) -> Path:
    p = Path(path).absolute()
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if p != p.resolve() or p.is_symlink() or getattr(p.stat(), 'st_file_attributes', 0) & 0x400:
        raise EdgeRejected('private directory indirection')
    return p

def write_new(path: str | Path, raw: bytes) -> None:
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if read_regular(path, max(len(raw), 1)) != raw:
        raise EdgeRejected('write readback mismatch')

def replace_owned(path: str | Path, raw: bytes) -> None:
    p = Path(path)
    if p.is_symlink():
        raise EdgeRejected('replace symlink')
    fd, temporary = tempfile.mkstemp(prefix='.edge-', dir=p.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def identifier(value: str) -> str:
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value) is None:
        raise EdgeRejected('identifier')
    return value

def sha256_value(value: str) -> str:
    if type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise EdgeRejected('sha256')
    return value

@contextmanager
def exclusive_local_file(path: str | Path):
    """Advisory, local lock in a trusted directory; not a distributed lease."""
    p = Path(path)
    if p.is_symlink():
        raise EdgeRejected('lock symlink')
    stream = p.open('a+b')
    locked = False
    try:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise EdgeRejected('LOCK_BUSY') from exc
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
