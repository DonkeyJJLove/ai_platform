"""Deny-only observation gate and native R5 constructor integration."""
from __future__ import annotations
import math
import threading
import time
from cyber_lion.mission_control.edge_support import EdgeRejected, object_bytes, read_regular, sha256_value
from .evidence import verify

class YokeGate:
    def __init__(self, *, snapshot, host_id, public_key, policy_sha256, clock=time.time, max_ttl=15):
        self.snapshot, self.host = snapshot, host_id
        self.public, self.policy = public_key, sha256_value(policy_sha256)
        self.clock, self.max_ttl = clock, max_ttl
        self.last_seq = 0
        self.lock = threading.Lock()

    def require_clear(self):
        try:
            frame = verify(object_bytes(read_regular(self.snapshot, 65536)), self.public)
        except (ValueError, OSError) as exc:
            raise EdgeRejected('YOKE_UNAVAILABLE_OR_UNTRUSTED') from exc
        if (frame.get('schema') != 'lion.edge.veto/v2' or frame.get('host_id') != self.host
                or frame.get('policy_sha256') != self.policy):
            raise EdgeRejected('YOKE_BINDING_MISMATCH')
        a, b, n, now = frame.get('observed_at'), frame.get('expires_at'), frame.get('seq'), self.clock()
        if (any(type(x) not in (int, float) or not math.isfinite(x) for x in (a,b,now))
                or not a <= now < b or not 0 < b-a <= self.max_ttl):
            raise EdgeRejected('YOKE_STALE')
        if type(n) is not int or n < 1:
            raise EdgeRejected('YOKE_SEQUENCE_INVALID')
        with self.lock:
            if n < self.last_seq:
                raise EdgeRejected('YOKE_ROLLBACK')
            self.last_seq = n
        if frame.get('state') != 'NO_VETO' or frame.get('authority_effect') != 'NONE':
            raise EdgeRejected('YOKE_VETO:'+str(frame.get('state')))
        return frame

class VetoBoundResolver:
    def __init__(self, canonical_resolver, gate):
        if not callable(canonical_resolver) or not isinstance(gate, YokeGate):
            raise EdgeRejected('canonical resolver and YokeGate required')
        self.inner, self.gate = canonical_resolver, gate

    def __call__(self, assignment_id):
        self.gate.require_clear()
        context = self.inner(assignment_id)
        self.gate.require_clear()
        return context

def attach_yoke(*, dependencies, gate):
    """Same repository, original R5 provider. This does not create its dependencies.

    R5 invokes context_source once to resolve, then again immediately before
    write. Long-lived guard, budgets, authority and currentness owners survive.
    """
    from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeWriterProvider
    if type(dependencies) is not dict or not callable(dependencies.get('context_source')):
        raise EdgeRejected('existing runtime dependencies required')
    return CooperativeRuntimeWriterProvider(**{**dependencies,
        'context_source': VetoBoundResolver(dependencies['context_source'], gate)})
