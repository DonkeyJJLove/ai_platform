"""Real SQLite/filesystem integration; authority sources are SYNTHETIC fixtures.

No live mission/admission is created by these tests. The resolver reads the same
canonical table names used by Mission Control and composes the R4 writer.
"""
from __future__ import annotations
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import unittest

from cyber_lion.tests import test_cooperative_runtime_composition as fixtures
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.enterprise.cooperative_context_resolver import (
    CooperativeContextPin, CooperativeContextResolutionError,
    PinnedCooperativeContextResolver, SCHEMA,
)
from tools.lion_cooperative_worker_adapter import cooperative_assignment_once


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


class CooperativeContextResolverTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CooperativeRuntimeCompositionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.base = Path(self.f.temp.name)
        self.db = self.base / 'mission-control.sqlite'
        self.directory = self.base / 'context-references'
        self.directory.mkdir()
        original = json.loads(self.f.claim['input_json'])
        original['capability'] = 'COOPERATIVE_ARTIFACT_PRODUCTION'
        self.f.payload = {**original, 'assignment_id': self.f.claim['assignment_id']}
        self.f.claim.update(input_json=raw(original).decode(), input_digest=sha256(raw(original)).hexdigest())
        self.f.binding = replace(self.f.binding, input_digest=self.f.claim['input_digest'])
        self.aid = self.f.claim['assignment_id']
        self.lpcl = 'RUN=FIXTURE_ONLY\nMATERIAL_RUNTIME=DOCKER_LOCAL_MODEL\n'
        self.lpcl_digest = sha256(self.lpcl.encode()).hexdigest()
        self.claim = {**self.f.claim, 'logical_drone_id': 'drone:1', 'phase_id': 'BUILD__COOP_WRITE',
                      'control_epoch': 1, 'context_revision': 0, 'plan_revision': 0, 'dispatch_authority': 'AUTONOMOUS'}
        with sqlite3.connect(self.db) as c:
            c.executescript('''
            CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,spec_digest TEXT);
            CREATE TABLE mission_process_specs(mission_id TEXT PRIMARY KEY,authority_state TEXT,lpcl_text TEXT,lpcl_digest TEXT);
            CREATE TABLE mission_execution_drivers(mission_id TEXT PRIMARY KEY,state TEXT,generation INTEGER,current_phase TEXT,lease_expires_at TEXT);
            CREATE TABLE mission_operator_control(mission_id TEXT PRIMARY KEY,control_owner TEXT,pause_latch INTEGER,stop_latch INTEGER,control_epoch INTEGER,context_revision INTEGER,plan_revision INTEGER);
            CREATE TABLE operator_capability_revocations(mission_id TEXT,capability TEXT,released_at TEXT);
            CREATE TABLE mission_execution_assignments(assignment_id TEXT PRIMARY KEY,mission_id TEXT,material_drone_id TEXT,logical_drone_id TEXT,phase_id TEXT,lease_generation INTEGER,state TEXT,lease_expires_at TEXT,input_json TEXT,input_digest TEXT,control_epoch INTEGER,context_revision INTEGER,plan_revision INTEGER,dispatch_authority TEXT);
            ''')
            c.execute('INSERT INTO missions VALUES(?,?,?)', ('M1', 'RUNNING', self.lpcl_digest))
            c.execute('INSERT INTO mission_process_specs VALUES(?,?,?,?)', ('M1', 'EXPLICIT_USER_ACTIVATION', self.lpcl, self.lpcl_digest))
            c.execute('INSERT INTO mission_execution_drivers VALUES(?,?,?,?,?)', ('M1', 'ACTIVE', 1, 'BUILD', '2026-10-05T00:00:00Z'))
            c.execute('INSERT INTO mission_operator_control VALUES(?,?,?,?,?,?,?)', ('M1', 'AUTONOMOUS', 0, 0, 1, 0, 0))
            names = tuple(self.claim)
            c.execute('INSERT INTO mission_execution_assignments (' + ','.join(names) + ') VALUES(' + ','.join('?' for _ in names) + ')', tuple(self.claim[n] for n in names))
        self.record = asdict(self.f.context(self.aid))
        ex = self.record['execution']
        ex['artifact_root'] = str(ex['artifact_root'])
        ex['admission_digest'] = ex.pop('admission')['admission_digest']
        self.record['schema'] = SCHEMA
        self.record['coordinates'] = {
            'assignment_id': self.aid, 'mission_id': 'M1', 'phase_id': 'BUILD__COOP_WRITE',
            'driver_phase_id': 'BUILD', 'worker_id': 'MD001', 'generation': 1,
            'control_epoch': 1, 'context_revision': 0, 'plan_revision': 0,
            'input_digest': self.claim['input_digest'], 'lpcl_digest': self.lpcl_digest,
        }
        self.path = self.directory / 'assignment.json'
        self.write_record()
        self.resolver = self.make_resolver()

    def write_record(self, data=None):
        self.path.write_bytes(raw(self.record) if data is None else data)
        self.pin = CooperativeContextPin(self.aid, self.path.name, sha256(self.path.read_bytes()).hexdigest())

    def make_resolver(self, **changes):
        args = dict(mission_db=self.db, context_directory=self.directory, pins=(self.pin,),
                    admission_source=self.f.source, admission_trust=rt.trust(),
                    dispatch_source=self.f.dispatch_source,
                    runtime_identity_source=lambda runtime: self.f.binding.identity,
                    now_fn=lambda: self.f.now)
        args.update(changes)
        return PinnedCooperativeContextResolver(**args)

    def sql(self, text, args=()):
        with sqlite3.connect(self.db) as c:
            c.execute(text, args)

    def denied(self, resolver=None):
        with self.assertRaises((ValueError, OSError)):
            (resolver or self.resolver)(self.aid)
        self.assertEqual(list(self.f.root.iterdir()), [])

    def test_reads_current_exact_context_without_changing_database(self):
        before = self.db.read_bytes()
        context = self.resolver(self.aid)
        self.assertEqual(context, self.f.context(self.aid))
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(list(self.f.root.iterdir()), [])

    def test_real_resolver_adapter_runtime_write_and_verifier(self):
        provider = self.f.make_provider(context_source=self.resolver)
        def control(op, args):
            if op == 'local_assignment_claim': return dict(self.claim)
            if op == 'local_assignment_receipt': return {'receipt_id': 'FIXTURE_RECEIPT', **args}
            raise AssertionError(op)
        receipt = cooperative_assignment_once(control, material_drone_id='MD001', artifact_root=self.f.root,
                    pending=[{**self.claim, 'state': 'READY'}], admitted_writer=provider, now_fn=lambda: self.f.now)
        self.assertEqual(receipt['status'], 'PASS', receipt)
        self.assertEqual((self.f.root/self.f.resource).read_bytes(), self.f.data)
        self.assertEqual(receipt['result']['runtime_receipt']['effect_state'], 'OBSERVED')
        from cyber_lion.mission_control.cooperative_artifacts import verify_text
        checked = verify_text(self.f.root, {'kind':'COOPERATIVE_ARTIFACT_VERIFY','mission_id':'M1',
            'source_assignment_id':self.aid,'generation':1,'artifact_name':'product.txt',
            'expected_sha256':sha256(self.f.data).hexdigest(),'expected_producer_worker_id':'MD001'},worker_id='MD002')
        self.assertTrue(checked['digest_match'])

    def test_unknown_assignment_cannot_select_context_file(self):
        with self.assertRaises(CooperativeContextResolutionError): self.resolver('assignment-other')

    def test_unknown_pin_does_not_create_database(self):
        missing = self.base/'missing.sqlite'
        with self.assertRaises((ValueError,OSError)): self.make_resolver(mission_db=missing)
        self.assertFalse(missing.exists())

    def test_duplicate_pins_rejected(self):
        with self.assertRaises(CooperativeContextResolutionError): self.make_resolver(pins=(self.pin,self.pin))

    def test_pin_filename_traversal_rejected(self):
        with self.assertRaises(CooperativeContextResolutionError): self.make_resolver(pins=(replace(self.pin,filename='../assignment.json'),))

    def test_tampered_context_bytes_rejected(self):
        self.path.write_bytes(self.path.read_bytes()+b' '); self.denied()

    def test_duplicate_context_json_keys_rejected(self):
        data=self.path.read_bytes(); self.write_record(b'{"schema":"wrong",'+data[1:]); self.denied(self.make_resolver())

    def test_embedded_admission_is_not_an_authority_source(self):
        self.record['execution']['admission'] = asdict(self.f.binding.admission)
        self.write_record();self.denied(self.make_resolver())

    def test_context_extra_fields_rejected(self):
        self.record['admitted']=True;self.write_record();self.denied(self.make_resolver())

    def test_nonfinite_context_rejected(self):
        self.record['coordinates']['generation']=float('nan');self.write_record();self.denied(self.make_resolver())

    def test_bool_generation_rejected(self):
        self.record['coordinates']['generation']=True;self.write_record();self.denied(self.make_resolver())

    def test_symlink_record_rejected(self):
        other=self.directory/'other.json';self.path.rename(other);self.path.symlink_to(other);self.denied()

    def test_pause_blocks_resolution(self):
        self.sql('UPDATE mission_operator_control SET pause_latch=1');self.denied()

    def test_stop_blocks_resolution(self):
        self.sql('UPDATE mission_operator_control SET stop_latch=1');self.denied()

    def test_control_owner_change_blocks_resolution(self):
        self.sql("UPDATE mission_operator_control SET control_owner='OPERATOR_PRIMARY'");self.denied()

    def test_control_epoch_change_blocks_resolution(self):
        self.sql('UPDATE mission_operator_control SET control_epoch=2');self.denied()

    def test_context_revision_change_blocks_resolution(self):
        self.sql('UPDATE mission_operator_control SET context_revision=1');self.denied()

    def test_plan_revision_change_blocks_resolution(self):
        self.sql('UPDATE mission_operator_control SET plan_revision=1');self.denied()

    def test_capability_revocation_blocks_resolution(self):
        self.sql('INSERT INTO operator_capability_revocations VALUES(?,?,NULL)',('M1','COOPERATIVE_ARTIFACT_PRODUCTION'));self.denied()

    def test_missing_revocation_table_is_not_assumed_empty(self):
        self.sql('DROP TABLE operator_capability_revocations');self.denied()

    def test_missing_control_row_blocks_resolution(self):
        self.sql('DELETE FROM mission_operator_control');self.denied()

    def test_missing_driver_blocks_resolution(self):
        self.sql('DELETE FROM mission_execution_drivers');self.denied()

    def test_driver_generation_change_blocks_resolution(self):
        self.sql('UPDATE mission_execution_drivers SET generation=2');self.denied()

    def test_driver_phase_change_blocks_resolution(self):
        self.sql("UPDATE mission_execution_drivers SET current_phase='OTHER'");self.denied()

    def test_expired_driver_lease_blocks_resolution(self):
        self.sql("UPDATE mission_execution_drivers SET lease_expires_at='2020-01-01T00:00:00Z'");self.denied()

    def test_expired_assignment_blocks_resolution(self):
        self.sql("UPDATE mission_execution_assignments SET lease_expires_at='2020-01-01T00:00:00Z'");self.denied()

    def test_canceled_assignment_blocks_resolution(self):
        self.sql("UPDATE mission_execution_assignments SET state='CANCELLED'");self.denied()

    def test_input_digest_tamper_blocks_resolution(self):
        self.sql("UPDATE mission_execution_assignments SET input_digest=?",('b'*64,));self.denied()

    def test_lpcl_bytes_tamper_blocks_resolution(self):
        self.sql("UPDATE mission_process_specs SET lpcl_text='other'");self.denied()

    def test_unactivated_lpcl_blocks_resolution(self):
        self.sql("UPDATE mission_process_specs SET authority_state='NONE'");self.denied()

    def test_unstarted_mission_blocks_resolution(self):
        self.sql("UPDATE missions SET state='AUTHORIZED'");self.denied()

    def test_replaced_database_blocks_resolution(self):
        alternate=self.base/'copy.sqlite';alternate.write_bytes(self.db.read_bytes());alternate.replace(self.db);self.denied()

    def test_live_runtime_identity_change_blocks_resolution(self):
        self.denied(self.make_resolver(runtime_identity_source=lambda _:replace(self.f.binding.identity,runtime_instance_id='other')))

    def test_dispatch_fence_change_blocks_resolution(self):
        self.f.dispatch_source.current=replace(self.f.fd,fencing_token='a'*64);self.denied()

    def test_stale_admission_blocks_resolution(self):
        self.f.source.current=False;self.denied()

    def test_forged_admission_blocks_resolution(self):
        self.f.source.admission=replace(self.f.binding.admission,admission_id='forged',admission_digest='').sealed();self.denied()

    def test_admission_source_substitution_blocks_resolution(self):
        self.f.source.source_instance_id='substituted';self.denied()

    def test_each_call_rechecks_control_state(self):
        self.resolver(self.aid);self.sql('UPDATE mission_operator_control SET pause_latch=1');self.denied()

    def test_references_only_do_not_consume_admission(self):
        self.resolver(self.aid);self.resolver(self.aid)
        receipt=self.f.write(provider=self.f.make_provider(context_source=self.resolver))
        self.assertEqual(receipt['runtime_receipt']['outcome'],'SUCCEEDED')

    def test_pause_after_resolution_before_write_is_rechecked(self):
        original=self.f.source.is_current
        calls=[]
        def current(digest):
            calls.append(digest)
            if len(calls)==2:self.sql('UPDATE mission_operator_control SET pause_latch=1')
            return original(digest)
        self.f.source.is_current=current
        provider=self.f.make_provider(context_source=self.resolver)
        with self.assertRaises(ValueError):self.f.write(provider=provider)
        self.assertEqual(list(self.f.root.iterdir()),[])
        self.sql('UPDATE mission_operator_control SET pause_latch=0')
        from cyber_lion.enterprise.runtime_execution import RuntimeExecutionError
        with self.assertRaises(RuntimeExecutionError):self.f.write(provider=provider)

    def test_changed_phase_after_resolution_prevents_filesystem_effect(self):
        original=self.f.source.is_current
        calls=[]
        def current(digest):
            calls.append(digest)
            if len(calls)==2:self.sql("UPDATE mission_execution_drivers SET current_phase='OTHER'")
            return original(digest)
        self.f.source.is_current=current
        with self.assertRaises(ValueError):self.f.write(provider=self.f.make_provider(context_source=self.resolver))
        self.assertEqual(list(self.f.root.iterdir()),[])

    def test_typed_publisher_reader_roundtrip(self):
        from cyber_lion.enterprise.cooperative_context_resolver import context_reference_bytes
        data=context_reference_bytes(self.f.context(self.aid),self.record['coordinates'])
        self.write_record(data)
        self.assertEqual(self.make_resolver()(self.aid),self.f.context(self.aid))
        self.assertNotIn('admission',json.loads(data)['execution'])
        self.assertEqual(list(self.f.root.iterdir()),[])

    def test_publisher_rejects_another_assignment(self):
        from cyber_lion.enterprise.cooperative_context_resolver import context_reference_bytes
        coords={**self.record['coordinates'],'assignment_id':'another-assignment'}
        with self.assertRaises(ValueError):context_reference_bytes(self.f.context(self.aid),coords)

    def test_effect_reference_must_match_existing_admission(self):
        self.record['execution']['effect']['proposal_id']='other-proposal'
        self.write_record();self.denied(self.make_resolver())

if __name__ == '__main__': unittest.main()
