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
    def test_illegal_complete_resume_fails(self):
        d.ensure_driver(self.c,'M1',now);d.activate(self.c,'M1',now);d.transition(self.c,'M1','COMPLETE',now)
        with self.assertRaises(ValueError): d.activate(self.c,'M1',now)
