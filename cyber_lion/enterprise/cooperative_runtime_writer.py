"""Cooperative artifact writer composed with the existing F009 execution engine.

No admission is issued here. The trusted composition root must resolve the exact
assignment to an existing RuntimeAdmission and provide its real engine. Missing
or stale admission fails in the existing engine before the filesystem backend.
This module does not add a scheduler, HTTP endpoint, authority store or shell.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission, RuntimeIdentityBinding, RequestedRuntimeEffect
from cyber_lion.contracts.runtime_execution import RuntimeExecutionRequest
from cyber_lion.contracts.executor_sandbox import SandboxRuntimeBinding
from cyber_lion.enterprise.runtime_execution import RuntimeExecutionEngine
from cyber_lion.enterprise.executor_sandbox import SandboxBackendWriteResult
from cyber_lion.mission_control.cooperative_artifacts import validate_write_payload, materialize_text, artifact_path


class CooperativeRuntimeWriterError(ValueError):
    pass


@dataclass(frozen=True)
class CooperativeExecutionBinding:
    assignment_id: str
    worker_id: str
    input_digest: str
    artifact_root: Path
    admission: RuntimeAdmission
    request: RuntimeExecutionRequest
    effect: RequestedRuntimeEffect
    identity: RuntimeIdentityBinding


class CooperativeArtifactBackend:
    """One frozen artifact operation under ExecutorSandbox, not a generic writer.

    Construct only inside the trusted runtime composition. The backend has no
    network/test execution surface. Real isolation remains a property of its
    provisioned workspace, OS identity and mounts, not this class name.
    """
    def __init__(self, *, root: Path, payload: Mapping[str, Any], worker_id: str,
                 runtime_binding: SandboxRuntimeBinding):
        runtime_binding.validate()
        self._metadata, self._data = validate_write_payload(payload, worker_id)
        self._payload = dict(payload)
        self._worker = worker_id
        self._root = Path(root)
        self._target = artifact_path(self._root, mission_id=self._metadata['mission_id'],
                                     generation=self._metadata['generation'], artifact_name=self._metadata['artifact_name'])
        self.resource = self._target.relative_to(self._root).as_posix()
        for key in ('backend_id','backend_identity_digest','backend_implementation_digest','sandbox_id','workspace_id'):
            setattr(self,key,getattr(runtime_binding,key))
        self.last_observation = None

    def write_file(self, path: str, payload: bytes) -> SandboxBackendWriteResult:
        if path != self.resource or type(payload) is not bytes or payload != self._data:
            raise CooperativeRuntimeWriterError('frozen artifact operation mismatch')
        observed = materialize_text(self._root, self._payload, worker_id=self._worker)
        self.last_observation = observed
        event = 'cooperative-artifact:' + self._metadata['assignment_id'] + ':' + observed['artifact_sha256']
        return SandboxBackendWriteResult(observed['artifact_sha256'], event, observed['artifact_path'])

    def read_file(self, path: str):
        raise CooperativeRuntimeWriterError('write-only artifact backend; separate verifier required')

    def run_test(self, path: str, command: tuple[str, ...]):
        raise CooperativeRuntimeWriterError('no process execution in artifact storage backend')


class CanonicalCooperativeWriter:
    """Concrete admitted_writer dependency for cooperative_assignment_once."""
    def __init__(self, *, engine: RuntimeExecutionEngine,
                 binding_source: Callable[[str], CooperativeExecutionBinding],
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        if type(engine) is not RuntimeExecutionEngine or not callable(binding_source):
            raise CooperativeRuntimeWriterError('canonical engine and binding source required')
        self._engine = engine
        self._source = binding_source
        self._now = now_fn

    def __call__(self, *, claimed, payload, artifact_root, worker_id):
        metadata, data = validate_write_payload(payload, worker_id)
        binding = self._source(metadata['assignment_id'])
        if type(binding) is not CooperativeExecutionBinding:
            raise CooperativeRuntimeWriterError('canonical assignment binding unavailable')
        r = binding.request
        r.validate()
        if (binding.assignment_id, binding.worker_id) != (metadata['assignment_id'], worker_id):
            raise CooperativeRuntimeWriterError('assignment/worker binding substitution')
        if (claimed.get('assignment_id'),claimed.get('material_drone_id'),claimed.get('mission_id'),claimed.get('lease_generation')) != (binding.assignment_id,worker_id,r.mission_id,r.generation):
            raise CooperativeRuntimeWriterError('claim coordinates differ from runtime request')
        if claimed.get('state') != 'CLAIMED' or type(claimed.get('lease_expires_at')) is not str:
            raise CooperativeRuntimeWriterError('claim state/expiry invalid')
        expires = datetime.fromisoformat(claimed['lease_expires_at'].replace('Z','+00:00'))
        now = self._now()
        if expires.tzinfo is None or now.tzinfo is None or now >= expires:
            raise CooperativeRuntimeWriterError('claim expired')
        # Validate exact original assignment JSON separately from the derived
        # write payload, which adds its assigned ID after the scheduler creates it.
        from tools.lion_cooperative_worker_adapter import assignment_input
        original = assignment_input(claimed)
        original_digest = sha256(json.dumps(original,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
        if binding.input_digest != original_digest or claimed.get('input_digest') != original_digest:
            raise CooperativeRuntimeWriterError('canonical input binding mismatch')
        if {**original,'assignment_id':binding.assignment_id} != dict(payload):
            raise CooperativeRuntimeWriterError('derived write payload substitution')
        root = Path(artifact_root)
        if root != binding.artifact_root or root != root.resolve(strict=True):
            raise CooperativeRuntimeWriterError('workspace root substitution')
        target = artifact_path(root, mission_id=metadata['mission_id'], generation=metadata['generation'], artifact_name=metadata['artifact_name'])
        if (r.mission_id,r.generation,r.action,r.resource,r.payload_digest,r.payload_size) != (metadata['mission_id'],metadata['generation'],'WRITE_FILE',target.relative_to(root).as_posix(),metadata['artifact_sha256'],len(data)):
            raise CooperativeRuntimeWriterError('artifact/runtime request mismatch')
        receipt = self._engine.execute(admission=binding.admission, request=r, effect=binding.effect,
                                       runtime_identity=binding.identity, payload=data)
        receipt.validate()
        if receipt.outcome != 'SUCCEEDED' or receipt.effect_state != 'OBSERVED' or receipt.effect_digest != metadata['artifact_sha256']:
            raise CooperativeRuntimeWriterError('runtime artifact effect not observed as success')
        return {**metadata,'artifact_path':str(target),'readback_match':True,
                'effect_receipt_digest':receipt.receipt_digest,
                'runtime_execution_id':receipt.execution_id,'runtime_admission_digest':receipt.admission_digest,
                'runtime_receipt':receipt.canonical_dict(),'authority_effect':'NONE'}
