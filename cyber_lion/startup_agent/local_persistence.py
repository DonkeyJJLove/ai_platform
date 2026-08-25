"""Fail-closed local persistence boundary for Startup Evolution artifacts.

R9D-2 closes direct startup-agent filesystem persistence paths.  A caller must supply an
exact target/purpose/payload-bound execution gate before the first write.  Gates are
single-use, writes are bounded to the admitted target, and success requires post-effect
observation of the exact bytes.  This boundary does not mint authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Lock

from .models import StartupModelError


def _digest(*parts: str) -> str:
    if not all(isinstance(x, str) and x.strip() for x in parts):
        raise StartupModelError("local persistence gate fields must be non-empty")
    return sha256(b"LION/STARTUP-LOCAL-PERSISTENCE/1\0" + "\0".join(parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LocalPersistenceGate:
    gate_event_id: str
    purpose: str
    target: str
    payload_digest: str
    nonce: str
    gate_digest: str

    @classmethod
    def seal(cls, *, gate_event_id: str, purpose: str, target: str | Path, payload: bytes, nonce: str) -> "LocalPersistenceGate":
        if not isinstance(payload, bytes):
            raise StartupModelError("local persistence payload must be bytes")
        target_text = str(Path(target).resolve())
        payload_digest = sha256(payload).hexdigest()
        gate_digest = _digest(gate_event_id, purpose, target_text, payload_digest, nonce)
        return cls(gate_event_id, purpose, target_text, payload_digest, nonce, gate_digest)

    def validate(self) -> "LocalPersistenceGate":
        if type(self) is not LocalPersistenceGate:
            raise StartupModelError("exact LocalPersistenceGate required")
        expected = _digest(self.gate_event_id, self.purpose, self.target, self.payload_digest, self.nonce)
        if self.gate_digest != expected:
            raise StartupModelError("local persistence gate digest mismatch")
        return self


@dataclass(frozen=True)
class LocalPersistenceObservation:
    target: str
    payload_digest: str
    observed_digest: str
    mode: str
    observed: bool


class LocalPersistenceObserver:
    """Read-after-write observer separated from the writer implementation."""

    def observe_replace(self, target: Path, payload: bytes) -> LocalPersistenceObservation:
        observed = target.read_bytes()
        return LocalPersistenceObservation(str(target), sha256(payload).hexdigest(), sha256(observed).hexdigest(), "replace", observed == payload)

    def observe_append(self, target: Path, payload: bytes) -> LocalPersistenceObservation:
        observed = target.read_bytes()
        return LocalPersistenceObservation(str(target), sha256(payload).hexdigest(), sha256(observed[-len(payload):]).hexdigest() if payload else sha256(b"").hexdigest(), "append", bool(payload) and observed.endswith(payload))


class LocalPersistenceBoundary:
    """Single enforcement point for startup-agent local persistent writes."""

    def __init__(self, *, observer: LocalPersistenceObserver | None = None) -> None:
        self._observer = observer or LocalPersistenceObserver()
        if type(self._observer) is not LocalPersistenceObserver:
            raise StartupModelError("exact local persistence observer required")
        self._lock = Lock()
        self._consumed: set[str] = set()

    def _admit(self, *, gate: LocalPersistenceGate, purpose: str, target: Path, payload: bytes) -> str:
        gate.validate()
        resolved = str(target.resolve())
        if gate.purpose != purpose or gate.target != resolved or gate.payload_digest != sha256(payload).hexdigest():
            raise StartupModelError("local persistence gate binding mismatch")
        with self._lock:
            if gate.gate_digest in self._consumed:
                raise StartupModelError("local persistence gate replay denied")
            self._consumed.add(gate.gate_digest)
        return gate.gate_digest

    def write_replace(self, *, target: str | Path, payload: bytes, purpose: str, gate: LocalPersistenceGate) -> LocalPersistenceObservation:
        path = Path(target).resolve()
        self._admit(gate=gate, purpose=purpose, target=path, payload=payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        observation = self._observer.observe_replace(path, payload)
        if not observation.observed or observation.payload_digest != observation.observed_digest:
            raise StartupModelError("local persistence replace observation failed")
        return observation

    def append(self, *, target: str | Path, payload: bytes, purpose: str, gate: LocalPersistenceGate) -> LocalPersistenceObservation:
        path = Path(target).resolve()
        if not payload:
            raise StartupModelError("local persistence append payload cannot be empty")
        self._admit(gate=gate, purpose=purpose, target=path, payload=payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
        observation = self._observer.observe_append(path, payload)
        if not observation.observed or observation.payload_digest != observation.observed_digest:
            raise StartupModelError("local persistence append observation failed")
        return observation
