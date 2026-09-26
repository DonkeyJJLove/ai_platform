"""Pure mission read projection. Observations and capabilities never grant authority."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from .phase_control import phase_capabilities

SCHEMA_VERSION = 'lion.mission-runtime/v1'
PROJECTION_VERSION = 'lion.mission-projection/v1'


def validate_registration(value):
    """Validate the existing intake contract before persistence, without activation."""
    if not isinstance(value, dict):
        raise ValueError('mission registration must be an object')
    for field in ('mission_id', 'title', 'objective', 'lpcl_digest', 'source_head', 'source_tree'):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError('mission registration missing ' + field)
    if not isinstance(value.get('description'), str):
        raise ValueError('mission registration description')
    if not isinstance(value.get('phases'), list) or not value['phases']:
        raise ValueError('mission registration phase plan required')
    for field in ('logical_count', 'material_target'):
        if type(value.get(field)) is not int or value[field] < 0:
            raise ValueError('mission registration ' + field)


def normalize_snapshot(snapshot):
    out = deepcopy(snapshot)
    process = out.get('process') or {}
    driver = out.get('execution_driver') or {}
    context = out.get('schema_context') or {}
    try:
        spec = json.loads(out.get('spec_json') or '{}')
    except (ValueError, TypeError):
        spec = {}
    if not isinstance(spec, dict):
        spec = {}
    historical = str(out.get('adapter') or '').startswith('LEGACY_OBSERVATION:') or context.get('record_class') in {'HISTORICAL_PRE_SCHEMA', 'HISTORICAL_PARTIAL_SCHEMA'}
    gaps = []

    def observed(field, value):
        if value is None:
            gaps.append({'field': field, 'reason': 'HISTORICAL_NOT_RECORDED' if historical else 'NOT_RECORDED'})
        return value

    phases = deepcopy(out.get('phases') or [])
    messages = out.get('protocol_messages') or []
    specs = {p['phase_id']: p for p in out.get('phase_execution_specs', [])}
    contracts = {p['phase_id']: p for p in out.get('phase_execution_contracts', [])}
    plans = {p['phase_id']: p for p in out.get('generic_phase_plans', [])}
    for phase in phases:
        phase_spec = specs.get(phase['phase_id'], {})
        phase['handler_id'] = phase_spec.get('handler_id')
        phase['handler_version'] = phase_spec.get('handler_version')
        totals = out.get('phase_evidence_counts')
        phase['evidence_count'] = totals.get(phase['phase_id'], 0) if isinstance(totals, dict) else sum(1 for m in messages if m.get('phase') == phase['phase_id'] and m.get('protocol') in {'EVIDENCE', 'VALIDATION', 'RECEIPT'})
        phase['evidence_count_scope'] = 'PERSISTED_TOTAL' if isinstance(totals, dict) else 'RECENT_MESSAGE_WINDOW'
        phase['blocker'] = driver.get('blocking_gate') if driver.get('current_phase') == phase['phase_id'] else (phase.get('detail') if phase.get('status') == 'BLOCKED' else None)
        phase['capabilities'] = phase_capabilities(out, phase['phase_id'])
        contract=contracts.get(phase['phase_id'],{})
        phase['completion_predicates']=deepcopy(contract.get('completion_predicates') or [])
        phase['currentness_requirements']=deepcopy(contract.get('currentness_requirements') or [])
        phase['evidence_requirements']=deepcopy(contract.get('evidence_requirements') or [])
        phase['contract_digest']=contract.get('contract_digest')
        plan=plans.get(phase['phase_id'],{})
        phase['plan_state']=plan.get('state')
        try: plan_evidence=json.loads(plan.get('evidence_json') or '{}') if isinstance(plan,dict) else {}
        except (ValueError,TypeError): plan_evidence={}
        phase['completion_checks']=deepcopy(plan_evidence.get('checks') or {})
    current = process.get('current_phase')
    if current is not None:
        reason = 'RECORDED_PROCESS_CURSOR'
    elif driver.get('state') in {'ACTIVE', 'WAITING', 'BLOCKED', 'PAUSED'} and any(p['phase_id'] == driver.get('current_phase') and p.get('status') in {'ACTIVE', 'RUNNING', 'WAITING', 'BLOCKED'} for p in phases):
        current = driver['current_phase']
        reason = 'RECORDED_DRIVER_CURSOR'
    else:
        active = [p['phase_id'] for p in phases if p.get('status') in {'ACTIVE', 'RUNNING'}]
        current = active[0] if len(active) == 1 else None
        reason = 'DERIVED_SINGLE_ACTIVE_PHASE' if len(active) == 1 else ('AMBIGUOUS_ACTIVE_PHASES' if active else 'NO_ACTIVE_PHASE_RECORDED')
    raw_runtime = out.get('runtime_state')
    material_state = None if str(raw_runtime or '').startswith('DRIVER_') else raw_runtime
    own_lineage = next((x for x in out.get('lineage', []) if x.get('mission_id') == out.get('mission_id')), {})
    normalized = {
        'schema_version': SCHEMA_VERSION, 'projection_version': PROJECTION_VERSION,
        'record_class': 'HISTORICAL_PARTIAL_SCHEMA' if historical else ('CURRENT_SCHEMA' if process else 'CURRENT_SCHEMA_INCOMPLETE'),
        'identity': {'mission_id': out.get('mission_id'), 'title': observed('identity.title', out.get('title')), 'adapter': out.get('adapter'), 'mission_class': observed('identity.mission_class', out.get('mission_class', spec.get('mission_class')))},
        'lineage': deepcopy(own_lineage),
        'authority': {'state': observed('authority.state', process.get('authority_state')), 'control_authority': out.get('control_authority'), 'projection_authority_effect': 'NONE'},
        'source': {'head': observed('source.head', out.get('source_head')), 'tree': observed('source.tree', out.get('source_tree')), 'updated_at': out.get('updated_at')},
        'objective': {'text': observed('objective.text', process.get('objective')), 'description': observed('objective.description', process.get('description'))},
        'fleet': {'logical_count': out.get('logical_count'), 'material_target': out.get('material_target'), 'materialized': out.get('materialized'), 'ready': out.get('ready'), 'logical_workers': deepcopy(out.get('logical') or []), 'material_workers': deepcopy(out.get('workers') or [])},
        'runtime': {'mission_state': out.get('state'), 'driver_state': driver.get('state'), 'material_state': observed('runtime.material_state', material_state), 'material_state_reason': 'RAW_VALUE_IS_DRIVER_STATE' if material_state is None and raw_runtime else 'RECORDED_VALUE', 'current_phase': current, 'current_phase_reason': reason, 'progress': observed('runtime.progress', process.get('progress'))},
        'phases': phases, 'receipts': deepcopy(out.get('action_receipts') or []),
        'environment': {'namespace': observed('environment.namespace', out.get('namespace')), 'hosts': observed('environment.hosts', out.get('hosts')), 'node': observed('environment.node', out.get('node')), 'image': observed('environment.image', out.get('image'))},
        'observability': {'events': deepcopy(messages), 'source_updated_at': out.get('updated_at'), 'event_window': 'RECORDED_RECENT_WINDOW', 'last_error': out.get('last_error')},
        'gaps': gaps,
    }
    for gap in context.get('missing_fields', []):
        entry = {'field': gap.get('field_name'), 'reason': 'HISTORICAL_NOT_RECORDED' if historical else gap.get('reason_class', 'NOT_RECORDED')}
        if entry not in gaps:
            gaps.append(entry)
    normalized['fleet']['assignment_history'] = deepcopy(out.get('execution_assignments') or [])
    normalized['fleet']['receipt_history'] = deepcopy(out.get('execution_receipts') or [])
    normalized['fleet']['history_window'] = deepcopy(out.get('execution_history_window') or {})
    revision = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    summary = {key: out.get(key) for key in ('mission_id', 'title', 'adapter', 'state', 'runtime_state', 'logical_count', 'material_target', 'materialized', 'ready', 'updated_at')}
    summary.update({'objective': process.get('objective'), 'current_phase': current, 'current_phase_reason': reason, 'progress': process.get('progress'), 'authority_state': process.get('authority_state'), 'record_class': normalized['record_class'], 'normalized_schema_version': SCHEMA_VERSION, 'projection_version': PROJECTION_VERSION, 'projection_revision': revision, 'controllable': any(str(c.get('state', '')).startswith('SUPPORTED') and c.get('effect') not in {'NONE', 'READ_ONLY_CURRENTNESS', 'HISTORICAL_SOURCE_REINDEX', 'CONTROL_DB_METADATA_ONLY'} for c in (out.get('capabilities') or {}).values())})
    out.update({'normalized_schema_version': SCHEMA_VERSION, 'projection_version': PROJECTION_VERSION, 'projection_revision': revision, 'normalized_runtime': normalized, 'mission_summary': summary})
    return out
