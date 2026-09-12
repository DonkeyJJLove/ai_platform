"""Pure E02 offline decoders. No collector, authentication, clock or authority."""
from dataclasses import dataclass
from datetime import datetime
import re

from .producer_records import (
    application_observation, local_runtime_observation, qualification_result)
from .source_candidates import SourceRejected, canonical, decode, digest, exact

TELEMETRY_LIMIT = 16384
MAX_INTEGER = 9007199254740991
_ID = re.compile(r"[A-Za-z0-9:_-]{1,128}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.[0-9]{1,9})?Z", re.ASCII)
_APP_FIELDS = ("thread_id", "turn_id", "host_id", "state", "observed_at")
_LOCAL_FIELDS = ("host_id", "boot_id", "pid", "started_at", "image_digest",
                 "model_digest", "configuration_digest", "observed_at")
_QUAL_FIELDS = ("task_class", "runtime_digest", "suite_digest", "policy_digest",
                "report_digest", "required_cases", "outcomes", "outcome", "scope")
_TELEMETRY_FIELDS = (
    "schema", "event_id", "producer_id", "runtime_id", "boot_id", "clock_id", "run_id",
    "sequence", "source_revision", "policy_revision", "event_kind", "operation_class",
    "monotonic_start_ns", "monotonic_end_ns", "duration_ns", "observed_at_utc",
    "clock_uncertainty_ns", "dropped_count", "provenance", "evidence_ref", "authority_effect")


def decode_source_payload(kind, raw):
    """Decode three existing observation domains, never a session or grant.

    Even a signed envelope's payload remains an observation here. Callers must
    separately establish origin and exact subject bindings before integration.
    """
    if type(kind) is not str or kind not in (
            "APP_TASK_OBSERVATION", "LOCAL_RUNTIME_OBSERVATION", "QUALIFICATION_RESULT"):
        raise SourceRejected("unsupported semantic domain")
    payload = decode(raw)
    try:
        if kind == "APP_TASK_OBSERVATION":
            exact(payload, _APP_FIELDS)
            result = application_observation(**payload)
        elif kind == "LOCAL_RUNTIME_OBSERVATION":
            exact(payload, _LOCAL_FIELDS)
            result = local_runtime_observation(**payload)
        else:
            exact(payload, _QUAL_FIELDS)
            cases = payload["required_cases"]
            if type(cases) is not list or not cases or any(type(x) is not str for x in cases):
                raise SourceRejected("required cases must be a nonempty string array")
            result = qualification_result(
                task_class=payload["task_class"], runtime_digest=payload["runtime_digest"],
                suite_digest=payload["suite_digest"], policy_digest=payload["policy_digest"],
                report_digest=payload["report_digest"], required_cases=tuple(cases),
                measured_results=payload["outcomes"])
        if result.payload_json != canonical(payload):
            raise SourceRejected("payload disagrees with derived contract")
        return result
    except (TypeError, ValueError, RecursionError) as exc:
        raise SourceRejected("invalid observation payload") from exc


def _identifier(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise SourceRejected("opaque ASCII identifier required")


def _integer(value):
    if type(value) is not int or not 0 <= value <= MAX_INTEGER:
        raise SourceRejected("bounded unsigned integer required")


@dataclass(frozen=True)
class PassiveTimingObservation:
    canonical_json: str

    @property
    def provenance_status(self):
        return "UNVERIFIED"

    @property
    def runtime_ready(self):
        return False

    @property
    def authority_effect(self):
        return "NONE"


def decode_passive_timing(raw):
    """Validate a bounded record without resolving evidence or granting trust.

    The original UTC fractional precision is preserved. No cross-clock arithmetic,
    freshness decision, replay consumption or provenance promotion is performed.
    """
    if type(raw) is not bytes or len(raw) > TELEMETRY_LIMIT:
        raise SourceRejected("telemetry byte limit exceeded")
    value = decode(raw)
    exact(value, _TELEMETRY_FIELDS)
    if value["schema"] != "lion.e02.passive-timing/v1" or value["authority_effect"] != "NONE":
        raise SourceRejected("invalid telemetry domain or authority effect")
    for name in ("event_id", "producer_id", "runtime_id", "boot_id", "clock_id", "run_id"):
        _identifier(value[name])
    for name in ("sequence", "dropped_count"):
        _integer(value[name])
    for name in ("source_revision", "policy_revision"):
        digest(value[name])
    if value["evidence_ref"] is not None:
        _identifier(value["evidence_ref"])
    if value["clock_uncertainty_ns"] is not None:
        _integer(value["clock_uncertainty_ns"])
    if value["provenance"] not in ("CALLER_SUPPLIED", "VERIFIED_EXTERNAL_SOURCE"):
        raise SourceRejected("invalid provenance declaration")
    if value["operation_class"] not in ("QUEUE", "VALIDATION", "LOCAL_COMPUTE", "IO", "UNSPECIFIED"):
        raise SourceRejected("unsupported operation class")
    stamp = value["observed_at_utc"]
    if type(stamp) is not str or _UTC.fullmatch(stamp) is None:
        raise SourceRejected("strict UTC timestamp required")
    try:
        datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise SourceRejected("invalid calendar timestamp") from exc
    start, end, duration = (value[k] for k in (
        "monotonic_start_ns", "monotonic_end_ns", "duration_ns"))
    if value["event_kind"] == "OPERATION_DURATION":
        for number in (start, end, duration):
            _integer(number)
        if end < start or duration != end - start:
            raise SourceRejected("inconsistent monotonic duration")
    elif value["event_kind"] == "OBSERVATION_GAP":
        if any(number is not None for number in (start, end, duration)) or value["dropped_count"] < 1:
            raise SourceRejected("invalid observation gap")
    else:
        raise SourceRejected("unsupported event kind")
    return PassiveTimingObservation(canonical(value))
