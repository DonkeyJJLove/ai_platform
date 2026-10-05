"""Signed observation -> original five-field Mission Control protocol input.

Trusted transport and readback are dependencies. This module neither declares
an HTTP endpoint nor makes model/observer output an authority command.
"""
from __future__ import annotations
from pathlib import Path
from cyber_lion.enterprise.edge_yoke.evidence import verify
from .edge_support import EdgeRejected, canonical, object_bytes, read_regular, write_new, replace_owned, digest, identifier, sha256_value, exclusive_local_file
FIELDS = {'host_id','mission_id','phase_id','conversation_id','binding_epoch','lane',
          'provider_session_ref','correlation_id','context_digest','generation','to_id'}

def project_event(raw, *, public_key, binding, now, max_age=60):
    if type(binding) is not dict or set(binding) != FIELDS:
        raise EdgeRejected('current route binding required')
    for k in FIELDS-{'binding_epoch','generation','context_digest'}:
        identifier(binding[k])
    for k in ('binding_epoch','generation'):
        if type(binding[k]) is not int or binding[k] < 1:
            raise EdgeRejected('binding epoch/generation')
    sha256_value(binding['context_digest'])
    env = object_bytes(raw, 65536)
    event = verify(env, public_key)
    if (event.get('schema') != 'lion.edge.correction-request/v2' or event.get('host_id') != binding['host_id']
            or event.get('authority_effect') != 'NONE'):
        raise EdgeRejected('observation identity')
    identifier(event.get('request_id'))
    sha256_value(event.get('evidence_head'))
    at = event.get('observed_at')
    if type(at) not in (int,float) or not 0 <= now-at <= max_age:
        raise EdgeRejected('stale correction')
    if event.get('type') not in {'REVIEW_REQUIRED','RESOURCE_RECOVERED'}:
        raise EdgeRejected('correction type')
    payload = dict(schema='lion.edge.protocol-evidence/v2', request_id=event['request_id'], route_binding=binding,
                   signed_observation=env, observation_sha256=digest(raw), authority_effect='NONE',
                   semantic_role='REVIEW_REQUEST_NOT_CONTROL_COMMAND')
    return dict(protocol='EVIDENCE', from_id='YOKE-'+binding['host_id'], to_id=binding['to_id'], phase=binding['phase_id'], payload=payload)

def deliver_once(raw, *, public_key, binding, now, private_delivery_dir, publish, readback):
    message = project_event(raw, public_key=public_key, binding=binding, now=now)
    if not callable(publish) or not callable(readback):
        raise EdgeRejected('existing protocol publisher/readback required')
    root = Path(private_delivery_dir)
    if not root.is_dir() or root != root.resolve():
        raise EdgeRejected('private delivery directory')
    rid, mid = message['payload']['request_id'], binding['mission_id']
    path = root/(rid+'.json')
    with exclusive_local_file(root/'delivery.lock'):
        if path.exists():
            raise EdgeRejected('prior attempt requires reconciliation, not replay')
        row = dict(request_id=rid, mission_id=mid, state='SEND_ATTEMPT', message_sha256=digest(canonical(message)), authority_effect='NONE')
        write_new(path, canonical(row))
        try:
            publish(mid, message)
            if canonical(readback(mid, rid)) != canonical(message['payload']):
                raise EdgeRejected('protocol payload readback mismatch')
        except Exception:
            replace_owned(path, canonical(dict(row, state='SEND_UNKNOWN')))
            raise
        result = dict(row, state='DELIVERY_OBSERVED', execution_control_performed=False)
        replace_owned(path, canonical(result))
        return result
