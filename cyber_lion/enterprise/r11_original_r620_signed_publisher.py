"""R11 create-only publication of PREISSUED original signed R6.20 records.

A genuine upstream issuer must supply ALREADY-SIGNED bytes. This module holds
NO private key and cannot issue authority or a PDP result. It is an effectful
candidate and MUST be activated only by the existing ORIGINAL control-plane
execution with independently current LiveAdmittedAuthority scoped to this
exact database and action. No import/constructor causes a database write.

The publisher refuses missing/non-private DB, missing schema, stale
operator/currentness, invalid Ed25519 signature/typed R6.20 records, missing
or incorrect original AuthorityGrant action/resource scope, duplicate
publication and ambiguous writes. After a committed write it requires
independent reader readback. No retry follows UNKNOWN.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
from typing import Any, Callable
import json
import re
import sqlite3

from cyber_lion.enterprise.authority_source import AuthorityLookupKey
from cyber_lion.enterprise.cooperative_runtime_preparer import (
    validate_cooperative_runtime_preparation_inputs,
)
from cyber_lion.enterprise.live_authority_admission import (
    LiveAdmittedAuthority, LiveAuthorityAdmission,
)
from cyber_lion.enterprise.r11_original_current_owner_builder import OriginalPreparationEvidenceTrust
from cyber_lion.enterprise.r11_original_r620_evidence_source import ReadOnlyOriginalR620EvidenceSource
from cyber_lion.enterprise.r11_signed_original_r620_parts import (
    SQLiteSignedOriginalR620PartsSource, OriginalR620PreparationParts,
    R11OriginalSignedPartsError, _private_file, _zoned,
)
from cyber_lion.contracts.action_runtime_binding import bind_allowed_action_to_runtime_inputs

SCHEMA="lion.r11.signed-original-r620-create-once/v1"
ACTION="PUBLISH_ORIGINAL_R620_SIGNED_PARTS"
REQUIRED_AUTHORITY="local_write"
_SHA40=re.compile(r"^[0-9a-f]{40}$")


class R11OriginalR620PublishError(RuntimeError):
    pass


class R11OriginalR620EffectUnknown(R11OriginalR620PublishError):
    """Write may have committed, no automatic replay is allowed."""


def _need(condition: bool, reason: str):
    if not condition:
        raise R11OriginalR620PublishError(reason)


def _identity(x):
    return tuple(getattr(x, n, None) for n in (
        "source_id","source_instance_id","implementation_digest",
        "trust_anchor_id","trust_anchor_digest",
    ))


@dataclass(frozen=True)
class OriginalSignedR620Row:
    assignment_id: str
    mission_id: str
    generation: int
    input_digest: str
    record_json: str
    signature_hex: str
    key_id: str


class CreateOnlyOriginalSignedR620Publisher:
    """Original, explicitly admitted PREISSUED record import, never signer."""

    def __init__(
        self, *,
        reader: SQLiteSignedOriginalR620PartsSource,
        original_preparation: ReadOnlyOriginalR620EvidenceSource,
        signed_row_source: object,
        signed_row_source_trust: OriginalPreparationEvidenceTrust,
        authority_owner: LiveAuthorityAdmission,
        now_fn: Callable[[], datetime],
        source_pr_number: int,
        source_base_sha: str,
        source_head_sha: str,
    ):
        _need(type(source_pr_number) is int and source_pr_number>=1
              and type(source_base_sha) is str and _SHA40.fullmatch(source_base_sha)
              and type(source_head_sha) is str and _SHA40.fullmatch(source_head_sha),
              "exact original publication release binding unavailable")
        _need(type(reader) is SQLiteSignedOriginalR620PartsSource,
              "original exact independent signed reader required")
        _need(type(original_preparation) is ReadOnlyOriginalR620EvidenceSource,
              "original bounded read-only R6.20 guard required")
        _need(type(signed_row_source_trust) is OriginalPreparationEvidenceTrust,
              "separate signed issuer source trust required")
        _need(_identity(signed_row_source)==signed_row_source_trust.binding()
              and callable(getattr(signed_row_source,"resolve_issued_exact",None)),
              "independent preissued R6.20 row source/trust missing")
        _need(_identity(signed_row_source)!=_identity(reader)
              and signed_row_source is not reader,
              "original issuer cannot alias downstream reader")
        _need(isinstance(authority_owner,LiveAuthorityAdmission),
              "original LiveAuthorityAdmission owner required")
        _need(callable(now_fn),"trusted original publisher clock required")
        _need(original_preparation.mission_id==reader.mission_id
              and original_preparation.worker_id==reader.worker_id
              and original_preparation.mission_db!=reader.db_path,
              "canonical assignment / original signed DB identity alias")
        _need(original_preparation._parts_trust.binding()==reader._trust.binding()
              and original_preparation._pdp is not reader,
              "original preparation source and issuer role mismatch")
        reader._check_table()
        self._reader=reader
        self._prep=original_preparation
        self._issuer=signed_row_source
        self._issuer_trust=signed_row_source_trust
        self._authority=authority_owner
        self._now=now_fn
        self._source_identity=(source_pr_number,source_base_sha,source_head_sha)
        self._store_inode=_private_file(reader.db_path,"original signed R6.20 DB")
        # NEVER initialize/alter a table here, even if an external operator
        # has not yet provisioned the private store.

    def _current_authority(
        self, admitted: LiveAdmittedAuthority, now: datetime,
    ) -> None:
        _need(type(admitted) is LiveAdmittedAuthority
              and admitted.repository=="DonkeyJJLove/ai_platform"
              and admitted.mission_id==self._reader.mission_id
              and admitted.authority_ceiling==REQUIRED_AUTHORITY
              and (admitted.pr_number,admitted.base_sha,admitted.head_sha)
                  ==self._source_identity,
              "original exact publication authority envelope missing")
        # This is the ORIGINAL authenticated signature/epoch/revocation gate,
        # not an authorization decision from the publisher's own output.
        try:
            matched=self._authority.revalidate(admitted,now=now)
        except Exception as exc:
            raise R11OriginalR620PublishError(
                "original publication authority is not current"
            ) from exc
        _need(type(matched) is LiveAdmittedAuthority and matched==admitted,
              "original publication authority substitution")
        key=AuthorityLookupKey(
            admitted.repository,admitted.pr_number,admitted.base_sha,
            admitted.head_sha,admitted.mission_id,admitted.grant_id,
        ).validate()
        try:
            original=self._authority._source.resolve_exact(key)
        except Exception as exc:
            raise R11OriginalR620PublishError(
                "original publication grant source unavailable"
            ) from exc
        _need(
            original is not None and len(getattr(original,"lineage",()))>=1
            and getattr(original,"lookup_key",None) is not None
            and original.lookup_key.binding()==key.binding(),
            "original publication grant lineage unavailable",
        )
        leaf=original.lineage[-1]
        _need(
            ACTION in getattr(leaf,"actions",())
            and str(self._reader.db_path) in getattr(leaf,"resource_scope",())
            and getattr(leaf,"mission_id",None)==admitted.mission_id
            and getattr(leaf,"authority_ceiling",None)==REQUIRED_AUTHORITY,
            "original signed publication action/resource not admitted",
        )

    def publish(
        self, assignment_id: str, *,
        admitted: LiveAdmittedAuthority, trusted_now: datetime,
    ) -> str:
        stamp=_zoned(trusted_now,"original R6.20 publisher trusted_now")
        local=_zoned(self._now(),"original R6.20 publisher current clock")
        _need(0 <= (local-stamp).total_seconds() <= 5,
              "original publisher time not current")
        self._reader._check_table()
        self._current_authority(admitted,stamp)
        before=self._prep._snapshot(assignment_id)
        _need(_identity(self._issuer)==self._issuer_trust.binding(),
              "original issuer source drift before issue")
        try:
            issued=self._issuer.resolve_issued_exact(
                assignment_id,before["mission_id"],before["lease_generation"],
                before["input_digest"],stamp,
            )
        except Exception as exc:
            raise R11OriginalR620PublishError(
                "independent original preissued record unavailable"
            ) from exc
        _need(_identity(self._issuer)==self._issuer_trust.binding(),
              "original issuer source drift after issue")
        _need(type(issued) is OriginalSignedR620Row,
              "original signed issuer row exact type required")
        _need(
            (issued.assignment_id,issued.mission_id,issued.generation,
             issued.input_digest)==(
                 assignment_id,before["mission_id"],before["lease_generation"],
                 before["input_digest"],
             ),
            "original issuer assignment/generation/input substitution",
        )
        try:
            parts=self._reader.verify_preissued(
                assignment_id=issued.assignment_id,
                mission_id=issued.mission_id,
                generation=issued.generation,input_digest=issued.input_digest,
                trusted_now=stamp,raw=issued.record_json,
                signature=issued.signature_hex,key_id=issued.key_id,
            )
            evidence=parts.evidence()
            validate_cooperative_runtime_preparation_inputs(
                assignment=before,artifact_root=self._prep.artifact_root,
                evidence=evidence,
            )
            _effect,_identity_binding,bound_pdp=bind_allowed_action_to_runtime_inputs(
                evidence.proposal,evidence.proposal_context,evidence.pdp_result,
                evidence.currentness,evidence.provisioned_executor,
            )
            actual=self._prep._pdp.resolve(
                evidence.pdp_result.applied.request_id,
                evidence.pdp_result.applied.gate_event_id,
            )
            policy=self._prep._pdp.current_policy_binding(
                evidence.pdp_result.applied.policy_binding,
            )
        except Exception as exc:
            raise R11OriginalR620PublishError(
                "original signed inputs fail canonical R6.20/PDP preflight"
            ) from exc
        _need(actual==bound_pdp
              and policy==evidence.pdp_result.applied.policy_binding,
              "original PDP/policy is stale or substituted")
        try:
            still_current=self._prep._snapshot(assignment_id)
        except Exception as exc:
            raise R11OriginalR620PublishError(
                "original operator/driver changed before publication"
            ) from exc
        _need(still_current==before,
              "original operator/driver changed before publication")
        _need(_identity(self._issuer)==self._issuer_trust.binding(),
              "original issuer drift before publication")
        write_now=_zoned(self._now(),"original publisher")
        _need(0 <= (write_now-stamp).total_seconds() <= 5,
              "original publication window elapsed before write")
        # Signature and nested original evidence were checked against the
        # captured issue time. Do not commit if the independently signed
        # lifetime expires while the original checks run.
        try:
            expiry=datetime.fromisoformat(
                json.loads(issued.record_json)["expires_at"]
            ).astimezone(timezone.utc)
        except (TypeError,ValueError,KeyError,AttributeError) as exc:
            raise R11OriginalR620PublishError(
                "signed original publication expiry unavailable"
            ) from exc
        _need(write_now<expiry,"signed original publication expired before write")
        self._current_authority(admitted,write_now)
        try:
            still_current=self._prep._snapshot(assignment_id)
        except Exception as exc:
            raise R11OriginalR620PublishError(
                "original operator/driver changed at publication boundary"
            ) from exc
        _need(still_current==before,
              "original operator/driver changed at publication boundary")
        _need(_private_file(self._reader.db_path,"original signed R6.20 DB")
              ==self._store_inode,"original signed R6.20 store inode drift")
        uri="file:"+self._reader.db_path.as_posix()+"?mode=rw"
        try:
            # A publication is a consequential effect. No background retry,
            # fallback schema creation, replacement or duplicate publication.
            with closing(sqlite3.connect(
                uri,uri=True,timeout=3,isolation_level=None,
            )) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "INSERT INTO r11_original_r620_signed_parts "
                        "(assignment_id,mission_id,generation,input_digest,"
                        "record_json,signature_hex,key_id) VALUES(?,?,?,?,?,?,?)",
                        (issued.assignment_id,issued.mission_id,issued.generation,
                         issued.input_digest,issued.record_json,
                         issued.signature_hex,issued.key_id),
                    )
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
        except sqlite3.IntegrityError as exc:
            raise R11OriginalR620PublishError(
                "original signed R6.20 publication replay denied"
            ) from exc
        except sqlite3.Error as exc:
            raise R11OriginalR620EffectUnknown(
                "original signed R6.20 publication effect unknown: reconcile"
            ) from exc
        try:
            reloaded=self._reader.resolve_exact(
                issued.assignment_id,issued.mission_id,issued.generation,
                issued.input_digest,stamp,
            )
            _need(type(reloaded) is OriginalR620PreparationParts and reloaded==parts,
                  "readback original signed parts mismatch")
        except Exception as exc:
            raise R11OriginalR620EffectUnknown(
                "original signed R6.20 committed but independent readback unknown"
            ) from exc
        return sha256(issued.record_json.encode("utf-8")).hexdigest()
