from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .artifacts import describe_artifact

HISTORICAL_VKT_SUMMARY = Path('/var/lib/sentinelx/uploads/vkt-r3-lpcl-v2-final/final-summary.json')
HISTORICAL_VKT_VALIDATOR = Path('/var/lib/sentinelx/uploads/vkt-r3-validation/lpcl-v2-supervised-600s.json')
HISTORICAL_OSS_SUMMARY = Path('/var/lib/sentinelx/uploads/oss-repository-tests/itsdangerous/final-summary.json')
HISTORICAL_OSS_EVIDENCE = Path('/var/lib/sentinelx/uploads/oss-repository-tests/itsdangerous/final-evidence.json')
TERMINAL_LIFECYCLE = {'CLEANING', 'CLEANED'}


class Reconciler:
    def __init__(self, store, registry) -> None:
        self.store = store
        self.registry = registry
        self.errors: dict[str, str] = {}

    def _preserve_terminal_lifecycle(self, run: dict[str, Any]) -> dict[str, Any]:
        existing = self.store.get_run(str(run.get('run_id') or ''))
        if not existing or existing.get('status') not in TERMINAL_LIFECYCLE:
            return run
        # An adapter poll may have started before teardown and return after the
        # lifecycle event has already committed CLEANING/CLEANED. Such a late
        # runtime snapshot may enrich evidence but may not move lifecycle time
        # backwards. A later RUN_STARTED event is handled by the event stream,
        # not by this adapter guard, so a new incarnation remains possible.
        guarded = dict(run)
        guarded['status'] = existing['status']
        guarded['phase'] = existing.get('phase') or guarded.get('phase')
        guarded['cleanup'] = existing.get('cleanup') or {}
        if existing.get('verification_status') == 'VERIFIED':
            guarded['verification_status'] = 'VERIFIED'
        return guarded

    def poll_once(self) -> list[dict[str, Any]]:
        observed: list[dict[str, Any]] = []
        for adapter in self.registry.all():
            try:
                runs = adapter.poll()
                self.errors.pop(adapter.adapter_id, None)
                for run in runs:
                    run = self._preserve_terminal_lifecycle(run)
                    normalized = self.store.upsert_run(run)
                    for name, value in (normalized.get('metrics') or {}).items():
                        if value is not None:
                            self.store.add_metric(normalized['run_id'], name, value)
                    for name, value in (normalized.get('participants') or {}).items():
                        self.store.add_participant(normalized['run_id'], name, value)
                    for artifact in normalized.get('artifacts') or []:
                        if isinstance(artifact, dict) and artifact.get('artifact_id'):
                            self.store.add_artifact(normalized['run_id'], artifact)
                    for receipt in normalized.get('receipts') or []:
                        if isinstance(receipt, dict) and receipt.get('receipt_id'):
                            self.store.add_receipt(normalized['run_id'], receipt)
                    observed.append(normalized)
                self.store.set_adapter_state(adapter.adapter_id, {'ok': True, 'last_poll': time.time(), 'run_count': len(runs)})
            except Exception as exc:
                message = type(exc).__name__ + ':' + str(exc)[:1000]
                self.errors[adapter.adapter_id] = message
                self.store.set_adapter_state(adapter.adapter_id, {'ok': False, 'last_poll': time.time(), 'error': message})
        return observed

    def import_known_history(self) -> dict[str, Any]:
        imported: list[str] = []
        errors: list[str] = []
        if HISTORICAL_VKT_SUMMARY.is_file():
            try:
                summary = json.loads(HISTORICAL_VKT_SUMMARY.read_text())
                validator = json.loads(HISTORICAL_VKT_VALIDATOR.read_text()) if HISTORICAL_VKT_VALIDATOR.is_file() else {}
                run_id = str(summary.get('run') or 'historical-vkt-r3')
                self.store.upsert_run({
                    'run_id': run_id,
                    'process_language': 'LPCL-1_0',
                    'process_class': 'VKT_R3_384_DRONE_TEST',
                    'adapter_type': 'VKT_R3',
                    'status': str(summary.get('final_status') or 'UNKNOWN').upper(),
                    'verification_status': 'VERIFIED' if summary.get('validation_600s_pass') is True else 'CORROBORATED',
                    'phase': 'COMPLETE',
                    'started_at': None,
                    'finished_at': summary.get('test_finished_unix'),
                    'duration': summary.get('validator_elapsed'),
                    'host': 'LION-AUTH-LAB',
                    'runtime': 'K3S',
                    'namespace': 'vkt-r3',
                    'source': {'repository': 'DonkeyJJLove/ai_platform', 'head': summary.get('source_head'), 'tree': summary.get('source_tree')},
                    'target': {'kind': 'VKT_R3_384_DRONE_FLEET'},
                    'workload': {'kind': 'KubernetesFleet', 'pods': 384},
                    'authority': {'class': 'BOUNDED_PRIVILEGED_ADMISSION', 'mission_control': 'READ_ONLY'},
                    'metrics': {
                        'ready': 384 if summary.get('pre_cleanup_checks', {}).get('ready_384') else None,
                        'uids': 384 if summary.get('pre_cleanup_checks', {}).get('unique_uid_384') else None,
                        'restarts': 0 if summary.get('pre_cleanup_checks', {}).get('restarts_0') else None,
                        'cases_proven': 36 if summary.get('pre_cleanup_checks', {}).get('cases_proven_36') else None,
                        'messages': 768 if summary.get('pre_cleanup_checks', {}).get('messages_768') else None,
                        'ack_rate': 1.0 if summary.get('pre_cleanup_checks', {}).get('ack_rate_1') else None,
                        'validator_elapsed': summary.get('validator_elapsed'),
                        'vendor_requests': summary.get('vendor_requests'),
                    },
                    'participants': {},
                    'cleanup': {'status': summary.get('cleanup_status'), 'confirm_status': summary.get('cleanup_confirm_status')},
                    'evidence': {'class': 'HISTORICAL_IMPORTED_EVIDENCE', 'baseline_uid_set': summary.get('baseline_uid_set'), 'validator_errors': validator.get('errors')},
                })
                self.store.add_artifact(run_id, describe_artifact(run_id, HISTORICAL_VKT_SUMMARY, 'ARTIFACT_HASH'))
                if HISTORICAL_VKT_VALIDATOR.is_file():
                    self.store.add_artifact(run_id, describe_artifact(run_id, HISTORICAL_VKT_VALIDATOR, 'ARTIFACT_HASH'))
                imported.append(run_id)
            except Exception as exc:
                errors.append('VKT:' + type(exc).__name__ + ':' + str(exc)[:500])
        if HISTORICAL_OSS_SUMMARY.is_file():
            try:
                summary = json.loads(HISTORICAL_OSS_SUMMARY.read_text())
                evidence = json.loads(HISTORICAL_OSS_EVIDENCE.read_text()) if HISTORICAL_OSS_EVIDENCE.is_file() else {}
                run_id = str(summary.get('run') or 'historical-oss-itsdangerous')
                if run_id == 'LION-LPCL-1_0-BOUNDED-OSS-REPOSITORY-K3S-AUTONOMOUS-TEST-v1':
                    run_id = 'historical-oss-itsdangerous-v1'
                self.store.upsert_run({
                    'run_id': run_id,
                    'process_language': 'LPCL-1_0',
                    'process_class': 'AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST',
                    'adapter_type': 'OSS_REPOSITORY_TEST',
                    'status': str(summary.get('final_status') or 'UNKNOWN').upper(),
                    'verification_status': 'VERIFIED' if summary.get('classification_checks', {}).get('cloned_head_exact') and summary.get('pytest_exit_code') == 0 else 'CORROBORATED',
                    'phase': 'COMPLETE',
                    'host': 'LION-AUTH-LAB',
                    'runtime': 'K3S',
                    'namespace': summary.get('k8s_namespace'),
                    'source': {'repository': 'DonkeyJJLove/ai_platform', 'head': summary.get('platform_source_head'), 'tree': summary.get('platform_source_tree')},
                    'target': {'repository': summary.get('target_repository'), 'commit': summary.get('target_commit'), 'cloned_head': summary.get('cloned_head')},
                    'workload': {'kind': 'KubernetesJob', 'job': summary.get('k8s_job'), 'pod_uid': summary.get('pod_uid')},
                    'authority': {'class': 'BOUNDED_PRIVILEGED_ADMISSION', 'mission_control': 'READ_ONLY'},
                    'metrics': {
                        'pytest_summary': summary.get('pytest_summary'),
                        'pytest_exit_code': summary.get('pytest_exit_code'),
                        'clone_exit_code': summary.get('clone_exit_code'),
                        'pod_restarts': summary.get('pod_restarts'),
                        'vendor_requests': summary.get('vendor_requests'),
                    },
                    'participants': {},
                    'cleanup': {'status': summary.get('cleanup_status'), 'confirm_status': summary.get('cleanup_confirm_status'), 'post_cleanup_status': summary.get('post_cleanup_status')},
                    'evidence': {'class': 'HISTORICAL_IMPORTED_EVIDENCE', 'job_status': evidence.get('job_status')},
                })
                self.store.add_artifact(run_id, describe_artifact(run_id, HISTORICAL_OSS_SUMMARY, 'ARTIFACT_HASH'))
                if HISTORICAL_OSS_EVIDENCE.is_file():
                    self.store.add_artifact(run_id, describe_artifact(run_id, HISTORICAL_OSS_EVIDENCE, 'ARTIFACT_HASH'))
                imported.append(run_id)
            except Exception as exc:
                errors.append('OSS:' + type(exc).__name__ + ':' + str(exc)[:500])
        return {'imported': imported, 'errors': errors}
