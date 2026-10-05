"""Finite qualification carrier; existing LPCL/assignment owners remain canonical."""
from __future__ import annotations
from pathlib import Path
import re
import time
from .edge_support import EdgeRejected, canonical, digest, read_regular, identifier, sha256_value
from .artifact_transfer import _binding
FIELDS = {'schema','scope','task_id','host_id','worker_id','operation','expires_at','input_sha256',
          'input_binding','output_binding','coordinates','use_local_model','executor_source_digest'}
COORDINATES = {'lane','provider_session_ref','message_id','correlation_id','causation_id','source_tree','context_bytes_sha256'}
WORKER_FILES = tuple('cyber_lion/mission_control/'+n for n in (
    '__init__.py','artifact_transfer.py','edge_support.py','edge_work_unit.py','edge_worker.py','edge_product.py'))
REPO = Path(__file__).resolve().parents[2]

def worker_digest():
    return digest(canonical({n:digest(read_regular(REPO/n)) for n in WORKER_FILES}))

def validate_work_unit(job, host_id, worker_id, now=None):
    now = time.time() if now is None else now
    if type(job) is not dict or set(job) != FIELDS or job.get('schema') != 'lion.edge.work-unit/v2':
        raise EdgeRejected('work unit fields')
    if job['scope'] != 'OPERATOR_QUALIFICATION':
        raise EdgeRejected('live missions require canonical R5 admission, not qualification CLI')
    for k in ('task_id','host_id','worker_id'):
        identifier(job[k])
    if (job['host_id'],job['worker_id']) != (host_id,worker_id):
        raise EdgeRejected('worker binding')
    if job['operation'] not in {'BUILD_INTEGRITY_TOOL','VERIFY_INTEGRITY_TOOL'}:
        raise EdgeRejected('unregistered operation')
    if type(job['expires_at']) not in (int,float) or not now < job['expires_at'] <= now+300:
        raise EdgeRejected('task lease')
    if type(job['use_local_model']) is not bool:
        raise EdgeRejected('model selection')
    if sha256_value(job['executor_source_digest']) != worker_digest():
        raise EdgeRejected('executor source drift')
    sha256_value(job['input_sha256'])
    ib, ob = _binding(job['input_binding']), _binding(job['output_binding'])
    if ob['assignment_id'] != job['task_id'] or ob['producer_ref'] != worker_id or ob['request_id'] != job['task_id']:
        raise EdgeRejected('output identity')
    for k in ('repository','source_head','mission_id','conversation_id','binding_epoch','generation','lease_generation','context_digest'):
        if ib[k] != ob[k]:
            raise EdgeRejected('lineage substitution:'+k)
    c = job['coordinates']
    if type(c) is not dict or set(c) != COORDINATES:
        raise EdgeRejected('coordinates')
    for k in ('lane','provider_session_ref','message_id','correlation_id','causation_id'):
        identifier(c[k])
    if re.fullmatch('[0-9a-f]{40}', c['source_tree']) is None:
        raise EdgeRejected('source tree')
    if c['message_id'] != job['task_id'] or c['causation_id'] != ib['request_id']:
        raise EdgeRejected('message/causation binding')
    if sha256_value(c['context_bytes_sha256']) != ib['context_digest']:
        raise EdgeRejected('context bytes binding')
    return job
