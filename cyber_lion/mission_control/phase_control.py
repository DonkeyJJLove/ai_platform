"""Containment-only controls for the recorded current phase's existing driver."""
import hashlib
import json
import re

KNOWN_HANDLERS = frozenset({'VERIFY_128L64M_BIND', 'VERIFY_SCHEDULER_SCHEMA', 'GLOBAL_MULTI_RUN_DISPATCH', 'VERIFY_LEASE_FAIRNESS', 'VERIFY_PHASE_PLAN', 'VERIFY_DRIVER_LIFECYCLE', 'VERIFY_UNKNOWN_HANDLER_WAIT'})


def phase_capabilities(snapshot, phase_id):
    process = snapshot.get('process') or {}
    driver = snapshot.get('execution_driver') or {}
    phase = next((p for p in snapshot.get('phases', []) if p.get('phase_id') == phase_id), None)
    spec = next((p for p in snapshot.get('phase_execution_specs', []) if p.get('phase_id') == phase_id), {})
    reason = None
    if str(snapshot.get('adapter') or '').startswith('LEGACY_OBSERVATION:'):
        reason = 'HISTORICAL_MISSION'
    elif snapshot.get('state') in {'SUPERSEDED', 'COMPLETE', 'STOPPED'}:
        reason = 'MISSION_NOT_ACTIVE'
    elif not phase or process.get('current_phase') != phase_id or driver.get('current_phase') != phase_id:
        reason = 'NOT_EXACT_CURRENT_PHASE'
    elif phase.get('status') not in {'RUNNING', 'WAITING', 'BLOCKED'}:
        reason = 'PHASE_NOT_ACTIVE'
    elif process.get('authority_state') != 'EXPLICIT_USER_ACTIVATION':
        reason = 'EXACT_ACTIVATION_REQUIRED'
    elif any(not isinstance(snapshot.get(k), str) or not re.fullmatch('[0-9a-f]{40}', snapshot[k]) for k in ('source_head', 'source_tree')):
        reason = 'EXACT_SOURCE_REQUIRED'
    elif spec.get('handler_id') not in KNOWN_HANDLERS:
        reason = 'UNKNOWN_PHASE_HANDLER'
    elif not driver.get('driver_id') or type(driver.get('generation')) is not int or driver['generation'] < 1:
        reason = 'DRIVER_GENERATION_REQUIRED'
    binding = {'mission_id': snapshot.get('mission_id'), 'phase_id': phase_id, 'phase_status': (phase or {}).get('status'), 'source_head': snapshot.get('source_head'), 'source_tree': snapshot.get('source_tree'), 'driver_id': driver.get('driver_id'), 'generation': driver.get('generation'), 'driver_state': driver.get('state'), 'authority_state': process.get('authority_state'), 'handler': spec.get('handler_id')}
    token = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    result = {'INSPECT': {'supported': phase is not None, 'effect': 'NONE', 'reason': None if phase else 'PHASE_NOT_FOUND', 'control_token': None}}
    for action, states in [('PAUSE', {'ACTIVE', 'WAITING', 'BLOCKED'}), ('STOP', {'ACTIVE', 'WAITING', 'BLOCKED', 'PAUSED'})]:
        why = reason or (None if driver.get('state') in states else 'DRIVER_STATE_NOT_ELIGIBLE')
        result[action] = {'supported': why is None, 'effect': 'CONTROL_STATE' if why is None else 'NONE', 'reason': why, 'control_token': token if why is None else None, 'scope': 'CURRENT_PHASE_DRIVER_CONTAINMENT'}
    return result


def apply_phase_action(mission_id, request, read_snapshot, mission_action):
    if type(request) is not dict or set(request) != {'phase_id', 'action', 'control_token'}:
        raise ValueError('phase containment request schema')
    action = request['action']
    if action not in {'PAUSE', 'STOP'}:
        raise ValueError('phase action unsupported')
    before = read_snapshot(mission_id)
    if before.get('mission_id') != mission_id:
        raise ValueError('phase mission identity mismatch')
    capability = phase_capabilities(before, request['phase_id'])[action]
    if not capability['supported']:
        raise ValueError(capability['reason'])
    if not isinstance(request['control_token'], str) or request['control_token'] != capability['control_token']:
        raise ValueError('stale phase control token')
    result = mission_action(mission_id, {'action': action, 'phase_id': request['phase_id'], 'control_token': request['control_token']}, phase_guard=request)
    after = read_snapshot(mission_id)
    if any(after.get(k) != before.get(k) for k in ('mission_id', 'source_head', 'source_tree')) or any((after.get('execution_driver') or {}).get(k) != (before.get('execution_driver') or {}).get(k) for k in ('driver_id', 'generation', 'current_phase')):
        raise ValueError('phase containment identity drift')
    expected = 'PAUSED' if action == 'PAUSE' else 'STOPPED'
    if (after.get('execution_driver') or {}).get('state') != expected:
        raise ValueError('phase containment readback mismatch')
    receipt = result.get('receipt') or {}
    matched = next((r for r in after.get('action_receipts', []) if r.get('receipt_id') == receipt.get('receipt_id') and r.get('receipt_digest') == receipt.get('receipt_digest') and r.get('status') == 'PASS' and r.get('action') == action), None)
    if not receipt.get('receipt_id') or not receipt.get('receipt_digest') or matched is None:
        raise ValueError('phase containment durable receipt missing')
    previous = next(p for p in before['phases'] if p['phase_id'] == request['phase_id'])
    current = next((p for p in after.get('phases', []) if p.get('phase_id') == request['phase_id']), {})
    if current.get('status') != previous.get('status'):
        raise ValueError('phase verdict changed during containment')
    return {**result, 'phase_id': request['phase_id'], 'readback': {'driver_state': expected, 'phase_status': current.get('status'), 'receipt_id': receipt['receipt_id']}, 'authority_effect': 'NONE'}


def fence_phase_action(connection, mission_id, request):
    """Hold the SQLite writer reservation through the caller's driver transition."""
    if type(request) is not dict or set(request) != {'phase_id', 'action', 'control_token'} or request.get('action') not in {'PAUSE', 'STOP'}:
        raise ValueError('phase containment request schema')
    connection.execute('BEGIN IMMEDIATE')
    try:
        mission = connection.execute('SELECT * FROM missions WHERE mission_id=?', (mission_id,)).fetchone()
        if mission is None:
            raise ValueError('mission not found')
        snapshot = dict(mission)
        snapshot['process'] = dict(connection.execute('SELECT * FROM mission_process_specs WHERE mission_id=?', (mission_id,)).fetchone() or {})
        snapshot['execution_driver'] = dict(connection.execute('SELECT * FROM mission_execution_drivers WHERE mission_id=?', (mission_id,)).fetchone() or {})
        snapshot['phases'] = [dict(row) for row in connection.execute('SELECT * FROM mission_phases WHERE mission_id=?', (mission_id,))]
        snapshot['phase_execution_specs'] = [dict(row) for row in connection.execute('SELECT * FROM mission_phase_execution_specs WHERE mission_id=?', (mission_id,))]
        capability = phase_capabilities(snapshot, request['phase_id'])[request['action']]
        if not capability['supported']:
            raise ValueError(capability['reason'])
        if request['control_token'] != capability['control_token']:
            raise ValueError('stale phase control token')
        return snapshot
    except Exception:
        connection.rollback()
        raise
