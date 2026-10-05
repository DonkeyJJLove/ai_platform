"""Signed local observations; external retained checkpoints detect tail truncation."""
from __future__ import annotations
import base64
from contextlib import closing
from pathlib import Path
import sqlite3
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cyber_lion.mission_control.edge_support import canonical, digest, object_bytes, read_regular, write_new, EdgeRejected
DOMAIN = b'LION/EDGE/OBSERVATION/2\0'
ZERO = '0' * 64

def public_hex(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

def new_key(private_path, public_path):
    if Path(private_path).exists() or Path(public_path).exists():
        raise EdgeRejected('key already exists')
    key = Ed25519PrivateKey.generate()
    write_new(private_path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    Path(private_path).chmod(0o600)
    write_new(public_path, public_hex(key).encode())
    return key

def read_key(path):
    key = serialization.load_pem_private_key(read_regular(path, 4096), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise EdgeRejected('Ed25519 key required')
    return key

def sign(payload, key):
    return dict(payload=payload, signature=base64.b64encode(key.sign(DOMAIN+canonical(payload))).decode('ascii'))

def verify(envelope, pinned_public):
    if type(envelope) is not dict or set(envelope) != {'payload', 'signature'} or type(envelope['payload']) is not dict:
        raise EdgeRejected('signed envelope fields')
    try:
        sig = base64.b64decode(envelope['signature'], validate=True)
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pinned_public)).verify(sig, DOMAIN+canonical(envelope['payload']))
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise EdgeRejected('signature rejected') from exc
    return envelope['payload']

class EvidenceJournal:
    def __init__(self, path):
        self.path = Path(path)
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, previous TEXT NOT NULL, digest TEXT NOT NULL, raw BLOB NOT NULL)')

    def append(self, event, key):
        with closing(sqlite3.connect(self.path, timeout=5)) as c, c:
            c.execute('PRAGMA synchronous=FULL')
            c.execute('BEGIN IMMEDIATE')
            prev = c.execute('SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1').fetchone()
            seq, previous = (prev[0]+1, prev[1]) if prev else (1, ZERO)
            payload = dict(schema='lion.edge.evidence/v2', seq=seq, previous=previous, event=event)
            raw = canonical(sign(payload, key))
            value = digest(raw)
            c.execute('INSERT INTO events VALUES(?,?,?,?)', (seq, previous, value, raw))
            return dict(seq=seq, digest=value)

    def export(self, limit=67108864):
        with closing(sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True)) as c:
            c.execute('PRAGMA query_only=ON')
            c.execute('BEGIN')
            chunks, total = [], 0
            for raw, in c.execute('SELECT raw FROM events ORDER BY seq'):
                total += len(raw)+1
                if total > limit:
                    raise EdgeRejected('journal export limit')
                chunks.append(bytes(raw)+b'\n')
        return b''.join(chunks)

    def audit(self, pinned_public, expected_head=None):
        return verify_export(self.export(), pinned_public, expected_head)

def verify_export(raw, pinned_public, expected_head=None):
    if type(raw) is not bytes or len(raw) > 67108864:
        raise EdgeRejected('export limit')
    seq, previous = 0, ZERO
    for line in raw.splitlines():
        env = object_bytes(line)
        payload = verify(env, pinned_public)
        if payload.get('schema') != 'lion.edge.evidence/v2' or payload.get('seq') != seq+1 or payload.get('previous') != previous:
            raise EdgeRejected('chain mismatch')
        previous = digest(canonical(env))
        seq += 1
    head = dict(seq=seq, digest=previous)
    if expected_head is not None and head != expected_head:
        raise EdgeRejected('independent checkpoint mismatch')
    return head
