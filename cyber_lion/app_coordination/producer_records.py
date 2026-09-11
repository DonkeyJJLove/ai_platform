"""E02 observation contracts and signature verification composition candidates.

No signing backend, keys, APP_SESSION attestation, grants or runtime activation.
Verification means a supplied backend checked a policy-bound record; it never
upgrades a local observation into an authenticated application session.
"""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from cyber_lion.enterprise.trusted_control_plane_providers import TrustedSignatureVerifierAdapter
from .source_candidates import (SourceRejected, SourceUnavailable, canonical, decode,
                                digest, exact, text, validate_subject, _timestamp)

KINDS = frozenset(("APP_TASK_OBSERVATION", "LOCAL_RUNTIME_OBSERVATION",
                   "QUALIFICATION_RESULT", "TASK_BINDING_RECORD"))
DOMAIN = "LION/E02/SOURCE-RECORD/1"


@dataclass(frozen=True)
class Observation:
    kind: str
    payload_json: str
    provenance: str = "CALLER_SUPPLIED_OBSERVATION_NOT_ATTESTATION"


def application_observation(*, thread_id, turn_id, host_id, state, observed_at):
    for value in (thread_id, turn_id, host_id, state):
        text(value)
    _timestamp(observed_at)
    return Observation("APP_TASK_OBSERVATION", canonical(dict(
        thread_id=thread_id, turn_id=turn_id, host_id=host_id,
        state=state, observed_at=observed_at)))


def local_runtime_observation(*, host_id, boot_id, pid, started_at, image_digest,
                              model_digest, configuration_digest, observed_at):
    for value in (host_id, boot_id):
        text(value)
    if type(pid) is not int or pid <= 0:
        raise SourceRejected("positive process id required")
    for value in (image_digest, model_digest, configuration_digest):
        digest(value)
    start, observed = _timestamp(started_at), _timestamp(observed_at)
    if start > observed:
        raise SourceRejected("process start follows observation")
    return Observation("LOCAL_RUNTIME_OBSERVATION", canonical(dict(
        host_id=host_id, boot_id=boot_id, pid=pid, started_at=started_at,
        image_digest=image_digest, model_digest=model_digest,
        configuration_digest=configuration_digest, observed_at=observed_at)))


def qualification_result(*, task_class, runtime_digest, suite_digest, policy_digest,
                         report_digest, required_cases, measured_results):
    text(task_class)
    for value in (runtime_digest, suite_digest, policy_digest, report_digest):
        digest(value)
    if (type(required_cases) is not tuple or not required_cases
            or len(set(required_cases)) != len(required_cases)):
        raise SourceRejected("unique frozen required cases required")
    for case in required_cases:
        text(case)
    exact(measured_results, required_cases)
    if any(type(value) is not str or value not in ("PASS", "FAIL", "UNKNOWN")
           for value in measured_results.values()):
        raise SourceRejected("explicit measured outcomes required")
    outcome = ("FAIL" if "FAIL" in measured_results.values() else
               "UNKNOWN" if "UNKNOWN" in measured_results.values() else "PASS")
    return Observation("QUALIFICATION_RESULT", canonical(dict(
        task_class=task_class, runtime_digest=runtime_digest, suite_digest=suite_digest,
        policy_digest=policy_digest, report_digest=report_digest,
        required_cases=required_cases, outcomes=measured_results,
        outcome=outcome, scope="SUPPLIED_MEASUREMENT_NOT_RUNTIME_QUALIFICATION")))


@dataclass(frozen=True)
class ProducerPolicy:
    producer_id: str
    instance_id: str
    implementation_digest: str
    boot_id: str
    key_id: str
    algorithm: str
    policy_revision: str
    allowed_kinds: tuple[str, ...]
    max_age_seconds: int = 300

    def validate(self):
        for value in (self.producer_id, self.instance_id, self.boot_id, self.key_id, self.algorithm):
            text(value)
        digest(self.implementation_digest)
        digest(self.policy_revision)
        if (type(self.allowed_kinds) is not tuple or not self.allowed_kinds
                or len(set(self.allowed_kinds)) != len(self.allowed_kinds)
                or not set(self.allowed_kinds).issubset(KINDS)):
            raise SourceRejected("unsupported producer record domain")
        if type(self.max_age_seconds) is not int or not 1 <= self.max_age_seconds <= 300:
            raise SourceRejected("bounded validity required")
        return self


@dataclass(frozen=True)
class KeyStatus:
    policy_revision: str
    key_id: str
    state: str
    version: int
    observed_at: str
    expires_at: str

    def validate_at(self, now):
        digest(self.policy_revision)
        text(self.key_id)
        if self.state != "ACTIVE" or type(self.version) is not int or self.version < 1:
            raise SourceRejected("key unavailable or revoked")
        issued, expires = _timestamp(self.observed_at), _timestamp(self.expires_at)
        if not issued <= now < expires or not 0 < (expires-issued).total_seconds() <= 300:
            raise SourceRejected("key status is stale")
        return self


@dataclass(frozen=True)
class VerifiedRecordCandidate:
    kind: str
    record_digest: str
    canonical_record: str
    key_status_version: int
    status: str = "SIGNATURE_CHECKED_NOT_RUNTIME_AUTHORITY"
    runtime_ready: bool = False


class RecordVerifier:
    """Uses existing verifier API and an explicitly supplied current key source.

    Bootstrap dependencies are trusted caller configuration, not request fields.
    The caller provides a durable sequence lower bound; this object is not the
    admission replay guard and does not persist or consume an execution token.
    Payload verification is structural (JSON object) and cryptographic delegation
    only. Kind-specific semantics must be checked by a separately supplied decoder
    before any future source integration; a checked envelope is not qualification.
    """
    def __init__(self, *, policy, signature_verifier, key_status_source):
        if type(policy) is not ProducerPolicy:
            raise SourceRejected("exact producer policy required")
        if type(signature_verifier) is not TrustedSignatureVerifierAdapter:
            raise SourceRejected("existing trusted signature adapter required")
        if not callable(key_status_source):
            raise SourceUnavailable("current key status source required")
        self.policy = policy.validate()
        self.verifier = signature_verifier
        self.key_status_source = key_status_source

    def _key_status(self, now):
        try:
            value = self.key_status_source(self.policy.key_id)
        except Exception as exc:
            raise SourceUnavailable("key status source unavailable") from exc
        if type(value) is not KeyStatus:
            raise SourceRejected("exact key status required")
        value.validate_at(now)
        if (value.key_id, value.policy_revision) != (self.policy.key_id, self.policy.policy_revision):
            raise SourceRejected("key policy mismatch")
        return value

    def verify(self, raw, *, expected_kind, expected_subject, trusted_now, minimum_sequence):
        if type(trusted_now) is not datetime or trusted_now.utcoffset() is None:
            raise SourceRejected("aware trusted time required")
        if type(minimum_sequence) is not int or minimum_sequence < 0:
            raise SourceRejected("durable sequence lower bound required")
        policy = self.policy.validate()
        backend, key_source = self.verifier, self.key_status_source
        if expected_kind not in policy.allowed_kinds:
            raise SourceRejected("unsupported record kind; APP_SESSION attestation is unavailable")
        validate_subject(expected_subject)
        envelope = decode(raw)
        exact(envelope, ("record", "signature", "key_id", "algorithm"))
        for field in ("signature", "key_id", "algorithm"):
            text(envelope[field])
        if (envelope["key_id"], envelope["algorithm"]) != (policy.key_id, policy.algorithm):
            raise SourceRejected("untrusted key or algorithm")
        record = envelope["record"]
        exact(record, ("schema", "domain", "kind", "producer_id", "instance_id",
                       "implementation_digest", "boot_id", "sequence", "policy_revision",
                       "subject", "observed_at", "issued_at", "expires_at", "payload"))
        expected = ("lion.e02.producer-record/v1", DOMAIN, expected_kind,
                    policy.producer_id, policy.instance_id, policy.implementation_digest,
                    policy.boot_id, policy.policy_revision)
        actual = tuple(record[k] for k in ("schema", "domain", "kind", "producer_id",
                    "instance_id", "implementation_digest", "boot_id", "policy_revision"))
        if actual != expected:
            raise SourceRejected("record producer/domain substitution")
        sequence = record["sequence"]
        if type(sequence) is not int or sequence < minimum_sequence:
            raise SourceRejected("producer sequence rollback")
        validate_subject(record["subject"])
        if record["subject"] != expected_subject:
            raise SourceRejected("exact task/runtime subject mismatch")
        observed = _timestamp(record["observed_at"])
        issued, expires = _timestamp(record["issued_at"]), _timestamp(record["expires_at"])
        if not observed <= issued <= trusted_now < expires:
            raise SourceRejected("record not current")
        if not 0 < (expires-observed).total_seconds() <= policy.max_age_seconds:
            raise SourceRejected("record exceeds freshness policy")
        if type(record["payload"]) is not dict:
            raise SourceRejected("payload object required")
        before = self._key_status(trusted_now)
        body = canonical(record)
        try:
            if backend.ready() is not True:
                raise SourceUnavailable("signature backend not ready")
            accepted = backend.verify(body.encode("utf-8"), envelope["signature"],
                                            policy.key_id, policy.algorithm)
        except Exception as exc:
            raise SourceRejected("signature verification failed closed") from exc
        if accepted is not True or self._key_status(trusted_now) != before:
            raise SourceRejected("signature invalid or key status changed")
        if (self.policy is not policy or self.verifier is not backend
                or self.key_status_source is not key_source or backend.ready() is not True):
            raise SourceRejected("verification configuration changed")
        return VerifiedRecordCandidate(expected_kind, sha256(body.encode()).hexdigest(),
                                       body, before.version)

    def resolve(self, *args, **kwargs):
        raise SourceUnavailable("production source activation is not implemented")
