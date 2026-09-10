import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_lion.mission_control.models import fleet_summary_from_runs
from cyber_lion.mission_control.reconciliation import Reconciler
from cyber_lion.mission_control.registry import AdapterRegistry
from cyber_lion.mission_control.server import MissionControl
from cyber_lion.mission_control.storage import Store


def snapshot(count=384, status='RUNNING'):
    return {'run_id': 'fleet', 'adapter_type': 'TEST', 'status': status,
            'metrics': {'pods': count, 'fresh_drones': count,
                        'fleet_organizations': {'LION': count} if count else {},
                        'active_by_organization': {'LION': count} if count else {}}}


class Adapter:
    adapter_id = 'TEST'
    supported_process_classes = ('TEST',)
    def __init__(self):
        self.runs = [snapshot()]
        self.fail = False
    def poll(self):
        if self.fail:
            raise RuntimeError('read unavailable')
        return self.runs


class FleetCurrentnessTests(unittest.TestCase):
    def test_terminal_and_historical_counts_are_not_current(self):
        for status in ('CLEANING', 'CLEANED'):
            self.assertIsNone(fleet_summary_from_runs([snapshot(status=status)])['working_drones'])
        run = snapshot()
        run['evidence'] = {'class': 'HISTORICAL_IMPORTED_EVIDENCE'}
        self.assertEqual(fleet_summary_from_runs([run])['currentness'], 'UNKNOWN')

    def test_zero_is_known_and_contradiction_is_unknown(self):
        self.assertEqual(fleet_summary_from_runs([snapshot(0)])['working_drones'], 0)
        run = snapshot()
        run['metrics']['fresh_drones'] = 0
        self.assertIsNone(fleet_summary_from_runs([run])['working_drones'])
        run = snapshot()
        run['metrics']['active_by_organization']['LION'] = 385
        self.assertEqual(fleet_summary_from_runs([run])['organizations'], {})

    def test_failed_empty_expired_and_cleaned_observations_are_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'mc.db')
            try:
                registry = AdapterRegistry()
                adapter = Adapter()
                registry.register(adapter)
                mc = MissionControl(store, registry, Reconciler(store, registry))
                self.assertIsNone(mc.summary()['fleet']['working_drones'])
                mc.poll_once()
                self.assertEqual(mc.summary()['fleet']['working_drones'], 384)
                with patch('cyber_lion.mission_control.server.time.monotonic', return_value=mc.last_poll_at + 6):
                    self.assertIsNone(mc.summary()['fleet']['working_drones'])
                store.upsert_run({'run_id': 'fleet', 'status': 'CLEANED'})
                self.assertIsNone(mc.summary()['fleet']['working_drones'])
                store.upsert_run({'run_id': 'fleet', 'status': 'RUNNING'})
                adapter.fail = True
                mc.poll_once()
                self.assertIsNone(mc.summary()['fleet']['working_drones'])
                adapter.fail = False
                adapter.runs = []
                mc.poll_once()
                self.assertIsNone(mc.summary()['fleet']['working_drones'])
                self.assertEqual(store.get_run('fleet')['metrics']['pods'], 384)
            finally:
                store.close()

    def test_empty_maps_replace_current_snapshot_without_erasing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'mc.db')
            try:
                registry = AdapterRegistry()
                adapter = Adapter()
                registry.register(adapter)
                mc = MissionControl(store, registry, Reconciler(store, registry))
                mc.poll_once()
                adapter.runs = [snapshot(0)]
                mc.poll_once()
                fleet = mc.summary()['fleet']
                self.assertEqual(fleet['fleet_total'], 0)
                self.assertEqual(fleet['working_drones'], 0)
                self.assertEqual(fleet['organizations'], {})
                self.assertEqual(store.get_run('fleet')['metrics']['fleet_organizations'], {'LION': 384})
            finally:
                store.close()
