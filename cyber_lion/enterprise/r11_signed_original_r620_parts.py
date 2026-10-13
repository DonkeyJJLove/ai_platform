"""Authenticated read-only original R6.20 twelve-part input source.

Reads ONLY independently signed immutable original input records from a
pre-provisioned private SQLite file. A public Ed25519 verifier key is pinned
independently by a protected original-service configuration (not by records).
This module cannot create an issuer, grant, PDP ALLOW, admission or effect.

No default trusted key, unsigned fallback, migration or self-attestation.
The actual external original service, authorized issuer and data producer must
be separately installed/admitted for production MD001. These assertions alone
cannot confer that provenance.
"""
from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints, Union
import json
import os
import re
import sqlite3
import stat
from contextlib import closing

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from cyber_lion.enterprise.cooperative_dependency_provider import _ReadOnlySQLite
from cyber_lion.enterprise.r11_original_current_owner_builder import (
    OriginalPreparationEvidenceTrust,
)
from cyber_lion.enterprise.r11_original_r620_evidence_source import (
    OriginalR620PreparationParts,
)

SCHEMA = "lion.r11.original-r620-signed-parts/v1"
DOMAIN = b"LION/ORIGINAL-R620-INPUT-PARTS/1\x00"
TABLE = "r11_original_r620_signed_parts"
COLUMNS = ("assignment_id", "mission_id", "generation", "input_digest",
           "record_json", "signature_hex", "key_id")
MISSION = "LION-APPLICATION-FACTORY-CROSS-MODEL-R1"
REPOSITORY = "DonkeyJJLove/ai_platform"
WORKER = "MD001"
MAX_BYTES = 262144
MAX_WINDOW_SECONDS = 300
_SHA = re.compile(r"^[a-f0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class R11OriginalSignedPartsError(RuntimeError):
    pass


def _need(ok: bool, reason: str):
    if not ok:
        raise R11OriginalSignedPartsError(reason)


def _distinct_pairs(pairs):
    result = {}
    for key, value in pairs:
        _need(type(key) is str and key not in result,
              "duplicate original signed input field")
        result[key] = value
    return result


def _json_default(obj):
    if type(obj) is datetime and obj.tzinfo is not None:
        return obj.astimezone(timezone.utc).isoformat()
    raise TypeError("unsupported original signed input field")


def canonical_record_bytes(record: dict) -> bytes:
    """Pure canonicalization only, not an evidence issuer/signing operation."""
    _need(type(record) is dict, "original signed input object required")
    try:
        content = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False, default=_json_default,
        ).encode("utf-8", "strict")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise R11OriginalSignedPartsError("original signed input JSON invalid") from exc
    _need(0 < len(content) <= MAX_BYTES, "original signed input byte limit")
    return content


@lru_cache(maxsize=50)
def _annotations(cls):
    return get_type_hints(cls)


def _reconstruct(tp, raw, label: str):
    """Strictly reconstruct known dataclass contracts; never eval/pickle/import."""
    if tp is datetime:
        _need(type(raw) is str, label+": timestamp type")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise R11OriginalSignedPartsError(label+": timestamp invalid") from exc
        _need(parsed.tzinfo is not None, label+": timestamp naive")
        return parsed
    if tp in (str, bool, int):
        _need(type(raw) is tp, label+": primitive type mismatch")
        return raw
    origin = get_origin(tp)
    args = get_args(tp)
    if origin in (UnionType, Union):
        choices=[]
        for member in args:
            if member is type(None) and raw is None:
                return None
            if member is type(None):
                continue
            try:
                choices.append(_reconstruct(member,raw,label))
            except R11OriginalSignedPartsError:
                continue
        _need(len(choices)==1, label+": union value invalid or ambiguous")
        return choices[0]
    if origin is tuple:
        _need(type(raw) is list, label+": tuple must be JSON array")
        if len(args)==2 and args[1] is Ellipsis:
            return tuple(_reconstruct(args[0],v,label) for v in raw)
        _need(len(raw)==len(args),label+": tuple arity invalid")
        return tuple(_reconstruct(t,v,label) for t,v in zip(args,raw))
    if is_dataclass(tp) and type(tp) is type:
        _need(type(raw) is dict,label+": dataclass object required")
        declared=fields(tp)
        expected={f.name for f in declared}
        _need(set(raw)==expected,label+": dataclass shape mismatch")
        annotations=_annotations(tp)
        kwargs={
            f.name:_reconstruct(annotations[f.name],raw[f.name],label+"."+f.name)
            for f in declared
        }
        try:
            return tp(**kwargs)
        except (TypeError,ValueError) as exc:
            raise R11OriginalSignedPartsError(label+": dataclass invalid") from exc
    raise R11OriginalSignedPartsError(label+": unsupported original field type")


def _private_file(file: Path, label: str) -> tuple[int,int]:
    _need(file.is_absolute() and not file.is_symlink(),label+": direct path required")
    try:
        parent = file.parent
        ps = parent.lstat()
        fs = file.lstat()
        _need(parent.resolve(strict=True)==parent
              and stat.S_ISDIR(ps.st_mode)
              and not (ps.st_mode & 0o022),
              label+": private parent required")
        _need(file.resolve(strict=True)==file
              and stat.S_ISREG(fs.st_mode) and fs.st_nlink==1
              and fs.st_uid in {os.geteuid(),0}
              and not (fs.st_mode & 0o077),
              label+": private single-link owner/path required")
    except OSError as exc:
        raise R11OriginalSignedPartsError(label+": missing") from exc
    return fs.st_dev,fs.st_ino


def _zoned(value: datetime, label: str) -> datetime:
    _need(type(value) is datetime and value.tzinfo is not None,
          label+": trusted zoned clock required")
    return value.astimezone(timezone.utc)


class SQLiteSignedOriginalR620PartsSource:
    """Private existing signed record reader with separate pinned root of trust."""

    def __init__(
        self, *,
        database: str | Path,
        source_trust: OriginalPreparationEvidenceTrust,
        public_key_path: str | Path,
        public_key_sha256: str,
        issuer_subject_id: str,
        issuer_key_id: str,
        now_fn,
        mission_id: str = MISSION,
        worker_id: str = WORKER,
    ):
        _need(type(source_trust) is OriginalPreparationEvidenceTrust,
              "original signed source trust required")
        binding=source_trust.binding()
        _need(type(mission_id) is str and mission_id==MISSION
              and type(worker_id) is str and worker_id==WORKER,
              "original signed input mission/worker scope invalid")
        for v,label in ((issuer_subject_id,"issuer subject"),
                        (issuer_key_id,"issuer key ID")):
            _need(type(v) is str and _ID.fullmatch(v) is not None,
                  label+" unbound")
        _need(type(public_key_sha256) is str
              and _SHA.fullmatch(public_key_sha256) is not None,
              "original independent public-key SHA pin required")
        _need(callable(now_fn),"original signed source clock required")
        self.db_path=Path(database)
        self._db_inode=_private_file(self.db_path,"original signed R6.20 DB")
        self._db=_ReadOnlySQLite(self.db_path)
        self.public_key_path=Path(public_key_path)
        self._key_inode=_private_file(self.public_key_path,"original issuer public key")
        key_bytes=self.public_key_path.read_bytes()
        _need(sha256(key_bytes).hexdigest()==public_key_sha256 and len(key_bytes)==32,
              "independent Ed25519 verifier key digest/length mismatch")
        try:
            self._key=Ed25519PublicKey.from_public_bytes(key_bytes)
        except ValueError as exc:
            raise R11OriginalSignedPartsError("invalid Ed25519 verification key") from exc
        self._pubkey_digest=public_key_sha256
        self._trust=source_trust
        self.source_id,self.source_instance_id,self.implementation_digest,\
            self.trust_anchor_id,self.trust_anchor_digest=binding
        self.issuer_subject_id=issuer_subject_id
        self.issuer_key_id=issuer_key_id
        self.mission_id=mission_id
        self.worker_id=worker_id
        self._now=now_fn
        self._check_private_origins()
        _zoned(self._now(),"original signed source")
        self._check_table()

    def _check_private_origins(self):
        _need(_private_file(self.db_path,"original signed R6.20 DB")==self._db_inode,
              "original signed R6.20 DB identity drift")
        _need(_private_file(self.public_key_path,"original issuer public key")==self._key_inode
              and sha256(self.public_key_path.read_bytes()).hexdigest()==self._pubkey_digest,
              "original issuer public-key identity drift")
        _need((self.source_id,self.source_instance_id,self.implementation_digest,
              self.trust_anchor_id,self.trust_anchor_digest)==self._trust.binding(),
              "signed R6.20 source/trust drift")

    def _check_table(self):
        self._check_private_origins()
        try:
            with closing(self._db.connect()) as db:
                info=db.execute("PRAGMA table_info(r11_original_r620_signed_parts)").fetchall()
        except sqlite3.Error as exc:
            raise R11OriginalSignedPartsError("signed R6.20 schema unavailable") from exc
        _need(tuple(row[1] for row in info)==COLUMNS
              and tuple(row[2] for row in info)==(
                "TEXT","TEXT","INTEGER","TEXT","TEXT","TEXT","TEXT"
              )
              and tuple(row[5] for row in info)[:4]==(1,2,3,4),
              "signed R6.20 immutable table schema mismatch")
        self._check_private_origins()

    def resolve_exact(
        self, assignment_id: str, mission_id: str, generation: int,
        input_digest: str, trusted_now: datetime,
    ) -> OriginalR620PreparationParts:
        _need(type(assignment_id) is str and _ID.fullmatch(assignment_id) is not None
              and type(mission_id) is str and mission_id==self.mission_id
              and type(generation) is int and 1<=generation<=2147483647
              and type(input_digest) is str and _SHA.fullmatch(input_digest) is not None,
              "original signed R6.20 request coordinates invalid")
        observed=_zoned(trusted_now,"original R6.21 signed input request")
        local=_zoned(self._now(),"original signed source")
        _need(0 <= (local-observed).total_seconds() <= 5,
              "signed source clock not current with original R6.21")
        self._check_private_origins()
        try:
            with closing(self._db.connect()) as db:
                rows=db.execute(
                    "SELECT record_json,signature_hex,key_id "
                    "FROM r11_original_r620_signed_parts "
                    "WHERE assignment_id=? AND mission_id=? "
                    "AND generation=? AND input_digest=? LIMIT 2",
                    (assignment_id,mission_id,generation,input_digest),
                ).fetchall()
        except sqlite3.Error as exc:
            raise R11OriginalSignedPartsError("original signed R6.20 lookup unavailable") from exc
        _need(len(rows)==1,"signed R6.20 record missing or ambiguous")
        raw,signature,key_id=rows[0]
        _need(type(raw) is str and 0 < len(raw.encode("utf-8")) <= MAX_BYTES
              and type(signature) is str and len(signature)==128
              and type(key_id) is str and key_id==self.issuer_key_id,
              "original signed R6.20 record fields invalid")
        try:
            record=json.loads(
                raw, object_pairs_hook=_distinct_pairs,
                parse_constant=lambda _:(_ for _ in ()).throw(
                    R11OriginalSignedPartsError("signed R6.20 nonfinite JSON")
                ),
            )
        except R11OriginalSignedPartsError:
            raise
        except (ValueError, TypeError, UnicodeError) as exc:
            raise R11OriginalSignedPartsError("signed R6.20 JSON invalid") from exc
        _need(type(record) is dict
              and set(record)=={
                "schema","repository","mission_id","worker_id","assignment_id",
                "generation","input_digest","source","issuer_subject_id",
                "issuer_key_id","issued_at","expires_at","parts",
              },
              "signed R6.20 record schema mismatch")
        _need(canonical_record_bytes(record).decode("utf-8")==raw,
              "signed R6.20 record not canonical")
        _need(record["schema"]==SCHEMA and record["repository"]==REPOSITORY
              and record["mission_id"]==mission_id and record["worker_id"]==self.worker_id
              and record["assignment_id"]==assignment_id
              and type(record["generation"]) is int and record["generation"]==generation
              and record["input_digest"]==input_digest
              and record["issuer_subject_id"]==self.issuer_subject_id
              and record["issuer_key_id"]==key_id
              and type(record["source"]) is list
              and tuple(record["source"])==self._trust.binding(),
              "signed R6.20 issuer/source/assignment substitution")
        try:
            self._key.verify(bytes.fromhex(signature), DOMAIN+raw.encode("utf-8"))
        except (ValueError,InvalidSignature) as exc:
            raise R11OriginalSignedPartsError("original R6.20 Ed25519 signature invalid") from exc
        try:
            issued=_zoned(datetime.fromisoformat(record["issued_at"]),"signed issue")
            expires=_zoned(datetime.fromisoformat(record["expires_at"]),"signed expiry")
        except (ValueError,TypeError,AttributeError) as exc:
            raise R11OriginalSignedPartsError("original signed time window invalid") from exc
        _need(issued <= observed < expires
              and 0 < (expires-issued).total_seconds() <= MAX_WINDOW_SECONDS,
              "signed R6.20 record expired or future")
        parts=_reconstruct(OriginalR620PreparationParts,record["parts"],"original R6.20")
        try:
            evidence=parts.evidence()
        except Exception as exc:
            raise R11OriginalSignedPartsError(
                "signed original R6.20 component binding invalid"
            ) from exc
        _need(evidence.proposal.mission_id==mission_id
              and evidence.currentness.trusted_now.astimezone(timezone.utc)==observed
              and evidence.currentness.issued_at.astimezone(timezone.utc)<=issued
              and expires<=evidence.currentness.expires_at.astimezone(timezone.utc),
              "signed original R6.20 payload/time substitution")
        self._check_private_origins()
        return parts
