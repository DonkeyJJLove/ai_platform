import sqlite3, unittest
from datetime import datetime, timezone
from cyber_lion.mission_control import execution_driver as d
from cyber_lion.mission_control import dual_result_join as j

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

class DualJoinTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,schema_id TEXT UNIQUE,applied_at TEXT,source_head TEXT,source_tree TEXT,migration_digest TEXT,note TEXT)')
        d.migrate(self.c,now)
    def tearDown(self): self.c.close()
    def test_marked_request_preserves_both_tasks_and_shared_suffix(self):
        q="TEST currentness\nLOCAL:\nThree local weaknesses. Do not read SaaS.\nSAAS:\nThree external risks. Do not read LOCAL.\nNa końcu pokaż obie odpowiedzi osobno."
        x=j.split_dual_request(q)
        self.assertIn('Three local weaknesses',x['local_prompt']);self.assertNotIn('Three external risks',x['local_prompt'])
        self.assertIn('Three external risks',x['saas_prompt']);self.assertNotIn('Three local weaknesses',x['saas_prompt'])
        self.assertIn('Na końcu',x['local_prompt']);self.assertIn('Na końcu',x['saas_prompt'])
    def test_join_requires_both_receipts(self):
        x=j.create_dual(self.c,'M1','P1','LOCAL:\nA\nSAAS:\nB',{'ready':64},now)
        j.link_saas_request(self.c,x['request_id'],'saas-1',now)
        j.record_response(self.c,x['request_id'],j.LOCAL_PROVIDER,'LOCAL_OK',now,transport='LOCAL')
        self.assertEqual(j.join_result(self.c,x['request_id'])['state'],'WAITING_RESPONSES')
        j.record_response(self.c,x['request_id'],j.SAAS_PROVIDER,'SAAS_OK',now,transport='MEDIATED')
        out=j.join_result(self.c,x['request_id']);self.assertEqual(out['state'],'JOINED');self.assertIn('LOCAL_OK',out['answer']);self.assertIn('SAAS_OK',out['answer'])
