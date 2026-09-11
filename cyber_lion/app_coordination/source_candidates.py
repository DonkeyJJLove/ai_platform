"""Inactive E02 source configuration and bounded, evidence-only file adapters.

Digest equality establishes consistency, never source authentication. Runtime
resolve is deliberately unavailable. No signing, provider import, admission,
network, dispatch or source registration is implemented here.
"""
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re

from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding

KINDS = ("task_binding", "request_index", "admission")
LIMIT = 262144


class SourceRejected(ValueError):
    pass


class SourceUnavailable(SourceRejected):
    pass


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise SourceRejected("unexpected or missing fields")


def text(value):
    if type(value) is not str or not value.strip() or len(value) > 2048 or "\0" in value:
        raise SourceRejected("invalid identifier")


def digest(value):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise SourceRejected("invalid sha256")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SourceRejected("duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise SourceRejected("input exceeds byte limit")
    def invalid_constant(_):
        raise SourceRejected("nonfinite JSON number")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=invalid_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise SourceRejected("invalid strict JSON") from exc
    if type(value) is not dict:
        raise SourceRejected("JSON object required")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _read(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(LIMIT + 1)
    except OSError as exc:
        raise SourceUnavailable("source file unavailable") from exc
    if len(raw) > LIMIT:
        raise SourceRejected("source exceeds byte limit")
    return raw


def _timestamp(value):
    text(value)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() is None:
            raise ValueError("naive time")
        return result
    except ValueError as exc:
        raise SourceRejected("aware timestamp required") from exc


SUBJECT_FIELDS = (
    "mission_id", "task_id", "runtime_instance_id", "task_class",
    "checkpoint_revision", "source_head", "session_record_digest",
    "qualification_digest", "task_digest", "provisioned_executor_digest",
)


def validate_subject(value):
    exact(value, SUBJECT_FIELDS)
    for key in SUBJECT_FIELDS[:4]:
        text(value[key])
    if type(value["checkpoint_revision"]) is not int or value["checkpoint_revision"] < 0:
        raise SourceRejected("invalid checkpoint revision")
    if type(value["source_head"]) is not str or re.fullmatch("[0-9a-f]{40}", value["source_head"]) is None:
        raise SourceRejected("exact Git head required")
    for key in SUBJECT_FIELDS[6:]:
        digest(value[key])


@dataclass(frozen=True)
class SourceSpec:
    locator: str | None
    snapshot_sha256: str | None
    trust: RuntimeAdmissionSourceTrustBinding | None


@dataclass(frozen=True)
class InactiveConfiguration:
    mission_id: str
    max_age_seconds: int
    sources: tuple[tuple[str, SourceSpec], ...]
    subject_json: str | None

    def gaps(self):
        result = [] if self.subject_json is not None else ["subject"]
        for kind, spec in self.sources:
            for name in ("locator", "snapshot_sha256", "trust"):
                if getattr(spec, name) is None:
                    result.append(kind + "." + name)
        return tuple(result)


def load_configuration(raw):
    config = decode(raw)
    exact(config, ("schema", "enabled", "mode", "mission_id",
                   "max_age_seconds", "subject", "sources"))
    if (config["schema"] != "lion.e02.inactive-sources/v1"
            or config["enabled"] is not False
            or config["mode"] != "INACTIVE_CANDIDATE"):
        raise SourceRejected("only disabled candidate configuration is supported")
    text(config["mission_id"])
    age = config["max_age_seconds"]
    if type(age) is not int or not 1 <= age <= 300:
        raise SourceRejected("max_age_seconds must be 1..300")
    subject = config["subject"]
    if subject is not None:
        validate_subject(subject)
        if subject["mission_id"] != config["mission_id"]:
            raise SourceRejected("configuration mission mismatch")
    exact(config["sources"], KINDS)
    sources = []
    for kind in KINDS:
        spec = config["sources"][kind]
        exact(spec, ("locator", "snapshot_sha256", "trust"))
        locator = spec["locator"]
        if locator is not None:
            text(locator)
            path = PurePosixPath(locator)
            if (path.is_absolute() or "\\" in locator or ":" in locator
                    or any(part in ("", ".", "..") for part in locator.split("/"))
                    or path.suffix != ".json"):
                raise SourceRejected("relative JSON locator required")
        pin = spec["snapshot_sha256"]
        if pin is not None:
            digest(pin)
        trust = spec["trust"]
        if trust is not None:
            exact(trust, ("source_id", "source_instance_id", "source_implementation_digest",
                          "trust_anchor_id", "trust_anchor_digest", "schema_version"))
            try:
                trust = RuntimeAdmissionSourceTrustBinding(**trust).validate()
            except (ValueError, TypeError) as exc:
                raise SourceRejected("invalid canonical source trust binding") from exc
        sources.append((kind, SourceSpec(locator, pin, trust)))
    # The index and canonical receipt store may share a trust domain, not identity.
    index, receipt = dict(sources)["request_index"], dict(sources)["admission"]
    if (index.trust is not None and receipt.trust is not None
            and (index.trust.source_id, index.trust.source_instance_id)
            == (receipt.trust.source_id, receipt.trust.source_instance_id)):
        raise SourceRejected("request index and admission source must be distinct")
    return InactiveConfiguration(config["mission_id"], age, tuple(sources),
                                 None if subject is None else canonical(subject))


@dataclass(frozen=True)
class CandidateInspection:
    kind: str
    key: str
    payload_json: str
    snapshot_sha256: str
    status: str = "CONSISTENT_UNAUTHENTICATED_CANDIDATE"
    dispatch_allowed: bool = False


class CandidateSource:
    """File reader for offline review, not an authenticated runtime source.

    decode_payload is an explicitly supplied trusted composition dependency for
    existing task-binding/index contracts. Configuration cannot name/import code.
    A caller must not promote CandidateInspection into runtime evidence.
    """
    def __init__(self, config, kind, root, *, decode_payload=None):
        if type(config) is not InactiveConfiguration or kind not in KINDS:
            raise SourceRejected("inactive configuration and known source kind required")
        self.config, self.kind = config, kind
        self.root = Path(root).resolve(strict=True)
        self.spec = dict(config.sources)[kind]
        self.decode_payload = decode_payload

    def resolve(self, *args, **kwargs):
        raise SourceUnavailable("runtime source activation is not implemented")

    def inspect(self, key, trusted_now):
        digest(key)
        if type(trusted_now) is not datetime or trusted_now.utcoffset() is None:
            raise SourceRejected("aware observation time required")
        spec = self.spec
        if self.config.subject_json is None or any(x is None for x in
                (spec.locator, spec.snapshot_sha256, spec.trust)):
            raise SourceUnavailable("source has unresolved configuration")
        path = (self.root / spec.locator).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise SourceRejected("source path escapes configured root")
        raw = _read(path)
        if sha256(raw).hexdigest() != spec.snapshot_sha256:
            raise SourceRejected("snapshot changed")
        snapshot = decode(raw)
        exact(snapshot, ("schema", "kind", "source_binding", "records"))
        if snapshot["schema"] != "lion.e02.source-snapshot/v1" or snapshot["kind"] != self.kind:
            raise SourceRejected("source kind or schema mismatch")
        if snapshot["source_binding"] != asdict(spec.trust):
            raise SourceRejected("source binding mismatch")
        records = snapshot["records"]
        if type(records) is not list or len(records) > 1024:
            raise SourceRejected("bounded record list required")
        seen, selected = set(), None
        subject = json.loads(self.config.subject_json)
        for record in records:
            exact(record, ("key", "subject", "issued_at", "expires_at", "payload"))
            digest(record["key"])
            if record["key"] in seen:
                raise SourceRejected("duplicate record key")
            seen.add(record["key"])
            if record["key"] == key:
                selected = record
        if selected is None:
            raise SourceUnavailable("no canonical result; retry remains forbidden")
        validate_subject(selected["subject"])
        if selected["subject"] != subject:
            raise SourceRejected("session, qualification, task or runtime identity mismatch")
        issued, expires = _timestamp(selected["issued_at"]), _timestamp(selected["expires_at"])
        if not issued <= trusted_now < expires:
            raise SourceRejected("record not current")
        if not 0 < (expires - issued).total_seconds() <= self.config.max_age_seconds:
            raise SourceRejected("record freshness interval exceeds policy")
        payload = selected["payload"]
        if type(payload) is not dict:
            raise SourceRejected("payload object required")
        try:
            if self.kind == "admission":
                value = RuntimeAdmission(**payload).validate()
                if (value.admission_digest != key
                        or value.provisioned_executor_digest != subject["provisioned_executor_digest"]):
                    raise SourceRejected("receipt identity mismatch")
            else:
                if not callable(self.decode_payload):
                    raise SourceUnavailable("canonical payload decoder not configured")
                value = self.decode_payload(payload)
                if not is_dataclass(value) or isinstance(value, type):
                    raise SourceRejected("canonical dataclass required")
                if self.kind == "task_binding":
                    value.validate()
                    from cyber_lion.app_coordination.task_assignment import seal
                    if seal(value) != key:
                        raise SourceRejected("task binding digest mismatch")
                    binding = value
                else:
                    value.task_binding.validate()
                    value.runtime_admission.validate()
                    digest(value.source_revision)
                    binding = value.task_binding
                    if value.runtime_admission.provisioned_executor_digest != binding.provisioned_executor_digest:
                        raise SourceRejected("index task/receipt mismatch")
                if (binding.task_digest != subject["task_digest"]
                        or binding.qualification_digest != subject["qualification_digest"]
                        or binding.provisioned_executor_digest != subject["provisioned_executor_digest"]):
                    raise SourceRejected("task binding subject mismatch")
            payload_json = canonical(asdict(value))
        except (AttributeError, TypeError, ValueError) as exc:
            if isinstance(exc, SourceRejected):
                raise
            raise SourceRejected("canonical payload invalid") from exc
        return CandidateInspection(self.kind, key, payload_json, spec.snapshot_sha256)


def compare_index_receipt(index, receipt):
    """Compare separately inspected candidates, without changing any journal."""
    if (type(index) is not CandidateInspection or type(receipt) is not CandidateInspection
            or index.kind != "request_index" or receipt.kind != "admission"):
        raise SourceRejected("index and receipt inspections required")
    value = json.loads(index.payload_json)
    if value["runtime_admission"] != json.loads(receipt.payload_json):
        raise SourceRejected("index and canonical receipt differ")
    return "MATCH_UNAUTHENTICATED_NO_RETRY_OR_DISPATCH"


def main(argv=None):
    """Report inactive configuration gaps without reading source records."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configuration")
    args = parser.parse_args(argv)
    try:
        raw = _read(Path(args.configuration))
        config = load_configuration(raw)
        print(canonical({"configuration": "VALID_INACTIVE_CANDIDATE",
                         "sha256": sha256(raw).hexdigest(),
                         "missing": config.gaps(),
                         "runtime_ready": False, "dispatch_allowed": False}))
        return 0
    except SourceRejected as exc:
        print(canonical({"configuration": "REJECTED", "reason": str(exc),
                         "runtime_ready": False, "dispatch_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
