import sqlite3,tempfile,tracemalloc,unittest
from pathlib import Path
from cyber_lion.mission_control import operator_control

def now():return '2026-09-16T20:00:00Z'

class OperatorBackpressureTests(unittest.TestCase):
    def test_slow_consumer_has_bounded_page_and_independent_replay_cursor(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT)');c.execute("INSERT INTO missions VALUES('M','RUNNING')")
        operator_control.migrate(c,now);operator_control.ensure_primary_operator(c,now)
        for i in range(5000):operator_control._event(c,'M','TELEMETRY',{'seq':i},now)
        c.commit();tracemalloc.start();slow=operator_control.events_after(c,'M',0,limit=100);current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        self.assertEqual(len(slow['events']),100);self.assertEqual(slow['next_cursor'],100);self.assertLess(peak,2*1024*1024)
        fast=operator_control.events_after(c,'M',4900,limit=200);self.assertEqual(len(fast['events']),100);self.assertEqual(fast['next_cursor'],5000)
        operator_control.acknowledge_events(c,'fast','M',5000,now)
        replay=operator_control.events_after(c,'M',slow['next_cursor'],limit=100);self.assertEqual(replay['events'][0]['event_id'],101)
        self.assertEqual(c.execute("SELECT event_id FROM operator_consumer_cursors WHERE consumer_id='fast'").fetchone()[0],5000)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM operator_events').fetchone()[0],5000)
        c.close()
if __name__=='__main__':unittest.main()
