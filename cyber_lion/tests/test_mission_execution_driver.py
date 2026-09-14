import sqlite3, unittest
from datetime import datetime, timezone
from cyber_lion.mission_control import execution_driver as d

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

class DriverTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:'); self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,schema_id TEXT UNIQUE,applied_at TEXT,source_head TEXT,source_tree TEXT,migration_digest TEXT,note TEXT)')
        d.migrate(self.c,now,source_head='a'*40,source_tree='b'*40)
    def tearDown(self): self.c.close()
    def test_driver_is_durable_and_attempts_are_receipted(self):
        x=d.ensure_driver(self.c,'M1',now);self.assertEqual(x['state'],'BOOTSTRAP_PAUSED')
        y=d.activate(self.c,'M1',now);self.assertEqual(y['state'],'ACTIVE')
        aid=d.begin_attempt(self.c,'M1','P1',now,preconditions={'x':1});self.assertTrue(aid.startswith('attempt-'))
        out=d.finish_attempt(self.c,aid,now,state='PASS',evidence={'ok':True});self.assertEqual(out['state'],'PASS')
        snap=d.snapshot(self.c,'M1');self.assertTrue(snap['heartbeat_at']);self.assertEqual(snap['latest_attempt']['state'],'PASS')
    def test_driver_lease_fences_second_owner(self):
        d.ensure_driver(self.c,'M1',now);first=d.activate(self.c,'M1',now,owner_id='owner-A',lease_seconds=60)
        self.assertEqual(first['lease_owner'],'owner-A')
        with self.assertRaisesRegex(ValueError,'lease held'):
            d.activate(self.c,'M1',now,owner_id='owner-B',lease_seconds=60)
        with self.assertRaisesRegex(ValueError,'lease not owned'):
            d.begin_attempt(self.c,'M1','P1',now,owner_id='owner-B')
        aid=d.begin_attempt(self.c,'M1','P1',now,owner_id='owner-A');self.assertTrue(aid.startswith('attempt-'))

    def test_illegal_complete_resume_fails(self):
        d.ensure_driver(self.c,'M1',now);d.activate(self.c,'M1',now);d.transition(self.c,'M1','COMPLETE',now)
        with self.assertRaises(ValueError): d.activate(self.c,'M1',now)
    def test_adaptive_plan_is_bounded_and_identity_preserving(self):
        self.c.execute('CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,pod_uid TEXT,logical_id TEXT,phase TEXT,ready INTEGER,restarts INTEGER,pod_ip TEXT,observed_at TEXT)')
        for i in range(64):
            lid=f"LD{(i%12)+1:02d}"
            self.c.execute('INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)',('M1',f'p{i:02d}',f'u{i:02d}',lid,'RUNNING',1,0,'10.0.0.1',now()))
        out=d.adaptive_worker_plan(self.c,'M1',preferred_roles=('LD03','LD01'),limit=16)
        self.assertEqual(out['selected_count'],16);self.assertEqual(out['unique_uid_count'],64);self.assertEqual(out['authority_effect'],'NONE')
        self.assertTrue(all(x['logical_id'] in {'LD03','LD01'} for x in out['selected'][:10]))
        with self.assertRaises(ValueError):d.adaptive_worker_plan(self.c,'M1',limit=17)
