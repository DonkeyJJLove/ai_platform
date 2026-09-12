"""E02 trust-bundle candidates; evidence composition without runtime authority.

All inputs are caller-supplied or externally verified evidence candidates. This
module performs deterministic binding and freshness/substitution checks only. It
installs no collector, trusted clock, sequence store, credential or runtime source.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json

from .producer_records import VerifiedRecordCandidate
from .source_candidates import SourceRejected, SourceUnavailable, canonical, decode, digest, text, _timestamp

DOMAIN = b"LION/E02/TRUST-BUNDLE-CANDIDATE/1\0"


def _short_window(observed_at, expires_at, now, *, maximum=300):
    observed, expires = _timestamp(observed_at), _timestamp(expires_at)
    if not observed <= now < expires:
        raise SourceRejected("trust evidence is not current")
    if not 0 < (expires-observed).total_seconds() <= maximum:
        raise SourceRejected("trust evidence validity window is unbounded")
    return observed, expires


def _sealed(value):
    body=canonical(asdict(value)).encode("utf-8")
    return sha256(DOMAIN+body).hexdigest()


@dataclass(frozen=True)
class ProducerProvenanceCandidate:
    producer_id: str
    instance_id: str
    implementation_digest: str
    policy_revision: str
    boot_id: str
    collector_id: str
    collector_instance_id: str
    evidence_digest: str
    observed_at: str
    expires_at: str
    trust_state: str = "CALLER_EVIDENCE_NOT_INDEPENDENTLY_ATTESTED"

    def validate_at(self, now):
        for value in (self.producer_id,self.instance_id,self.boot_id,self.collector_id,self.collector_instance_id): text(value)
        for value in (self.implementation_digest,self.policy_revision,self.evidence_digest): digest(value)
        if self.trust_state != "CALLER_EVIDENCE_NOT_INDEPENDENTLY_ATTESTED": raise SourceRejected("producer trust promotion")
        _short_window(self.observed_at,self.expires_at,now)
        return self

    def digest(self): return _sealed(self)


@dataclass(frozen=True)
class CollectorProvenanceCandidate:
    collector_id: str
    instance_id: str
    host_id: str
    boot_id: str
    implementation_digest: str
    configuration_digest: str
    evidence_digest: str
    observed_at: str
    expires_at: str
    trust_state: str = "CALLER_EVIDENCE_NOT_INDEPENDENTLY_ATTESTED"

    def validate_at(self, now):
        for value in (self.collector_id,self.instance_id,self.host_id,self.boot_id): text(value)
        for value in (self.implementation_digest,self.configuration_digest,self.evidence_digest): digest(value)
        if self.trust_state != "CALLER_EVIDENCE_NOT_INDEPENDENTLY_ATTESTED": raise SourceRejected("collector trust promotion")
        _short_window(self.observed_at,self.expires_at,now)
        return self

    def digest(self): return _sealed(self)


@dataclass(frozen=True)
class TrustedTimeCandidate:
    provider_id: str
    instance_id: str
    source_digest: str
    evidence_digest: str
    observed_at: str
    expires_at: str
    uncertainty_ms: int
    trust_state: str = "EXTERNAL_TIME_EVIDENCE_CANDIDATE"

    def validate_at(self, now):
        for value in (self.provider_id,self.instance_id): text(value)
        for value in (self.source_digest,self.evidence_digest): digest(value)
        if type(self.uncertainty_ms) is not int or not 0 <= self.uncertainty_ms <= 1000: raise SourceRejected("bounded time uncertainty required")
        if self.trust_state != "EXTERNAL_TIME_EVIDENCE_CANDIDATE": raise SourceRejected("time trust promotion")
        _short_window(self.observed_at,self.expires_at,now,maximum=60)
        return self

    def digest(self): return _sealed(self)


@dataclass(frozen=True)
class DurableSequenceCandidate:
    producer_id: str
    store_id: str
    boot_id: str
    previous_sequence: int
    sequence: int
    store_digest: str
    evidence_digest: str
    trust_state: str = "EXTERNAL_DURABLE_SEQUENCE_EVIDENCE_CANDIDATE"

    def validate(self):
        for value in (self.producer_id,self.store_id,self.boot_id): text(value)
        for value in (self.store_digest,self.evidence_digest): digest(value)
        if (type(self.previous_sequence) is not int or type(self.sequence) is not int
                or self.previous_sequence < 0 or self.sequence <= self.previous_sequence):
            raise SourceRejected("strict durable sequence advance required")
        if self.trust_state != "EXTERNAL_DURABLE_SEQUENCE_EVIDENCE_CANDIDATE": raise SourceRejected("sequence trust promotion")
        return self

    def digest(self): return _sealed(self)


@dataclass(frozen=True)
class AppSessionAttestationCandidate:
    """Externally attested APP_SESSION evidence candidate; never runtime admission."""
    session_id: str
    app_instance_id: str
    subject_digest: str
    provider_id: str
    provider_instance_id: str
    provider_implementation_digest: str
    trust_anchor_digest: str
    attestation_digest: str
    evidence_digest: str
    observed_at: str
    expires_at: str
    access_class: str = "APP_SESSION"
    trust_state: str = "EXTERNAL_APP_ATTESTATION_CANDIDATE_NOT_INDEPENDENTLY_VERIFIED_HERE"
    authority_effect: str = "NONE"
    runtime_effect: str = "NONE"

    def validate_at(self, now):
        for value in (self.session_id,self.app_instance_id,self.provider_id,self.provider_instance_id): text(value)
        for value in (self.subject_digest,self.provider_implementation_digest,self.trust_anchor_digest,self.attestation_digest,self.evidence_digest): digest(value)
        if self.access_class != "APP_SESSION": raise SourceRejected("APP_SESSION access class required")
        if self.trust_state != "EXTERNAL_APP_ATTESTATION_CANDIDATE_NOT_INDEPENDENTLY_VERIFIED_HERE":
            raise SourceRejected("app attestation trust promotion")
        if self.authority_effect != "NONE" or self.runtime_effect != "NONE":
            raise SourceRejected("app attestation candidate cannot grant authority or runtime")
        _short_window(self.observed_at,self.expires_at,now,maximum=120)
        return self

    def digest(self): return _sealed(self)


@dataclass(frozen=True)
class AppSessionTrustCandidate:
    session_id: str
    app_instance_id: str
    subject_digest: str
    attestation_candidate_digest: str
    trusted_time_digest: str
    binding_digest: str
    app_session_attestation: str = "PARTIAL_CANDIDATE_EXTERNAL_ATTESTER_REQUIRED"
    canonical_runtime_source: str = "NOT_ACTIVATABLE"
    runtime_activation: str = "NOT_AUTHORIZED_NOT_INSTALLED"
    runtime_ready: bool = False
    authority_effect: str = "NONE"
    runtime_effect: str = "NONE"

    def validate(self):
        for value in (self.subject_digest,self.attestation_candidate_digest,self.trusted_time_digest,self.binding_digest): digest(value)
        for value in (self.session_id,self.app_instance_id): text(value)
        if self.app_session_attestation != "PARTIAL_CANDIDATE_EXTERNAL_ATTESTER_REQUIRED":
            raise SourceRejected("app session trust promotion")
        if self.canonical_runtime_source != "NOT_ACTIVATABLE" or self.runtime_activation != "NOT_AUTHORIZED_NOT_INSTALLED":
            raise SourceRejected("app session runtime promotion")
        if self.runtime_ready is not False or self.authority_effect != "NONE" or self.runtime_effect != "NONE":
            raise SourceRejected("app session candidate cannot activate runtime")
        expected=sha256(DOMAIN+canonical({
            "session_id":self.session_id,
            "app_instance_id":self.app_instance_id,
            "subject_digest":self.subject_digest,
            "attestation_candidate_digest":self.attestation_candidate_digest,
            "trusted_time_digest":self.trusted_time_digest,
        }).encode()).hexdigest()
        if self.binding_digest != expected: raise SourceRejected("app session binding digest mismatch")
        return self


@dataclass(frozen=True)
class LocalRuntimeTrustCandidate:
    verified_record_digest: str
    producer_provenance_digest: str
    collector_provenance_digest: str
    trusted_time_digest: str
    durable_sequence_digest: str
    subject_digest: str
    sequence: int
    binding_digest: str
    producer_provenance: str = "PARTIAL_CANDIDATE"
    collector_provenance: str = "PARTIAL_CANDIDATE"
    app_session_attestation: str = "NOT_IMPLEMENTED"
    local_runtime_attestation: str = "PARTIAL_CANDIDATE"
    trusted_time: str = "PARTIAL_EXTERNAL_REQUIREMENT"
    durable_sequence: str = "PARTIAL_EXTERNAL_REQUIREMENT"
    replay_result_atomicity: str = "PARTIAL_NOT_END_TO_END"
    canonical_runtime_source: str = "NOT_ACTIVATABLE"
    runtime_activation: str = "NOT_AUTHORIZED_NOT_INSTALLED"
    runtime_ready: bool = False
    authority_effect: str = "NONE"
    runtime_effect: str = "NONE"

    def validate(self):
        for value in (self.verified_record_digest,self.producer_provenance_digest,self.collector_provenance_digest,
                      self.trusted_time_digest,self.durable_sequence_digest,self.subject_digest,self.binding_digest): digest(value)
        if type(self.sequence) is not int or self.sequence < 1: raise SourceRejected("positive bound sequence required")
        if self.runtime_ready is not False or self.authority_effect != "NONE" or self.runtime_effect != "NONE":
            raise SourceRejected("trust candidate cannot activate runtime")
        if self.app_session_attestation != "NOT_IMPLEMENTED" or self.canonical_runtime_source != "NOT_ACTIVATABLE":
            raise SourceRejected("unsupported trust promotion")
        expected=sha256(DOMAIN+canonical({
            "verified_record_digest":self.verified_record_digest,
            "producer_provenance_digest":self.producer_provenance_digest,
            "collector_provenance_digest":self.collector_provenance_digest,
            "trusted_time_digest":self.trusted_time_digest,
            "durable_sequence_digest":self.durable_sequence_digest,
            "subject_digest":self.subject_digest,
            "sequence":self.sequence,
        }).encode()).hexdigest()
        if self.binding_digest != expected: raise SourceRejected("trust binding digest mismatch")
        return self


def compose_local_runtime_trust(*, verified_record, producer, collector, trusted_time, durable_sequence, trusted_now):
    if type(verified_record) is not VerifiedRecordCandidate or verified_record.kind != "LOCAL_RUNTIME_OBSERVATION":
        raise SourceRejected("signature-checked local runtime record required")
    if verified_record.status != "SIGNATURE_CHECKED_NOT_RUNTIME_AUTHORITY" or verified_record.runtime_ready is not False:
        raise SourceRejected("verified record trust promotion")
    if sha256(verified_record.canonical_record.encode()).hexdigest() != verified_record.record_digest:
        raise SourceRejected("verified record digest mismatch")
    if type(trusted_now) is not datetime or trusted_now.utcoffset() is None: raise SourceRejected("aware trusted time required")
    if type(producer) is not ProducerProvenanceCandidate or type(collector) is not CollectorProvenanceCandidate:
        raise SourceRejected("exact provenance candidates required")
    if type(trusted_time) is not TrustedTimeCandidate or type(durable_sequence) is not DurableSequenceCandidate:
        raise SourceRejected("exact time and sequence candidates required")
    producer.validate_at(trusted_now); collector.validate_at(trusted_now); trusted_time.validate_at(trusted_now); durable_sequence.validate()
    record=decode(verified_record.canonical_record.encode())
    required=("schema","domain","kind","producer_id","instance_id","implementation_digest","boot_id","sequence","policy_revision","subject","observed_at","issued_at","expires_at","payload")
    if set(record) != set(required): raise SourceRejected("verified record shape changed")
    if (record["producer_id"],record["instance_id"],record["implementation_digest"],record["policy_revision"],record["boot_id"]) != (
            producer.producer_id,producer.instance_id,producer.implementation_digest,producer.policy_revision,producer.boot_id):
        raise SourceRejected("producer provenance substitution")
    if (producer.collector_id,producer.collector_instance_id,producer.boot_id) != (collector.collector_id,collector.instance_id,collector.boot_id):
        raise SourceRejected("collector provenance substitution")
    if (durable_sequence.producer_id,durable_sequence.boot_id,durable_sequence.sequence) != (producer.producer_id,producer.boot_id,record["sequence"]):
        raise SourceRejected("durable sequence substitution or rollback")
    subject_digest=sha256(canonical(record["subject"]).encode()).hexdigest()
    components={
        "verified_record_digest":verified_record.record_digest,
        "producer_provenance_digest":producer.digest(),
        "collector_provenance_digest":collector.digest(),
        "trusted_time_digest":trusted_time.digest(),
        "durable_sequence_digest":durable_sequence.digest(),
        "subject_digest":subject_digest,
        "sequence":record["sequence"],
    }
    binding=sha256(DOMAIN+canonical(components).encode()).hexdigest()
    return LocalRuntimeTrustCandidate(binding_digest=binding,**components).validate()


def compose_app_session_trust(*, attestation, trusted_time, trusted_now, expected_session_id, expected_app_instance_id, expected_subject_digest):
    if type(trusted_now) is not datetime or trusted_now.utcoffset() is None: raise SourceRejected("aware trusted time required")
    if type(attestation) is not AppSessionAttestationCandidate or type(trusted_time) is not TrustedTimeCandidate:
        raise SourceRejected("exact app attestation and trusted-time candidates required")
    for value in (expected_session_id,expected_app_instance_id): text(value)
    digest(expected_subject_digest)
    attestation.validate_at(trusted_now); trusted_time.validate_at(trusted_now)
    if (attestation.session_id,attestation.app_instance_id,attestation.subject_digest) != (
            expected_session_id,expected_app_instance_id,expected_subject_digest):
        raise SourceRejected("app session attestation substitution")
    components={
        "session_id":attestation.session_id,
        "app_instance_id":attestation.app_instance_id,
        "subject_digest":attestation.subject_digest,
        "attestation_candidate_digest":attestation.digest(),
        "trusted_time_digest":trusted_time.digest(),
    }
    binding=sha256(DOMAIN+canonical(components).encode()).hexdigest()
    return AppSessionTrustCandidate(binding_digest=binding,**components).validate()


def activate_runtime(*args, **kwargs):
    raise SourceUnavailable("E02 trust candidates cannot activate runtime")
