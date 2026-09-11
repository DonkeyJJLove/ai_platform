from __future__ import annotations
import json, sqlite3, threading, time
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,ts REAL NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,ts REAL,event_type TEXT,fleet TEXT,pod_uid TEXT,case_id TEXT,phase TEXT,message_id TEXT,correlation_id TEXT,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY,ts REAL,from_fleet TEXT,from_pod_uid TEXT,to_fleet TEXT,case_id TEXT,phase TEXT,correlation_id TEXT,parent_message_id TEXT,payload TEXT NOT NULL);
'''
class Store:
    def __init__(self,path: str):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock(); self.db=sqlite3.connect(self.path,check_same_thread=False); self.db.executescript(SCHEMA); self.db.commit()
    def persist(self,snapshot: dict):
        raw=json.dumps(snapshot,sort_keys=True,separators=(',',':'))
        with self.lock:
            self.db.execute('INSERT INTO snapshots(ts,payload) VALUES(?,?)',(time.time(),raw))
            for e in snapshot.get('events',[]):
                self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?,?,?)',(e.get('event_id'),e.get('timestamp'),e.get('event_type'),e.get('fleet'),e.get('pod_uid'),e.get('case_id'),e.get('phase'),e.get('message_id'),e.get('correlation_id'),json.dumps(e,sort_keys=True,separators=(',',':'))))
            for m in snapshot.get('messages',[]):
                self.db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?,?,?,?)',(m.get('message_id'),m.get('timestamp'),m.get('from_fleet'),m.get('from_pod_uid'),m.get('to_fleet'),m.get('case_id'),m.get('phase'),m.get('correlation_id'),m.get('parent_message_id'),json.dumps(m,sort_keys=True,separators=(',',':'))))
            self.db.commit()
    def latest(self):
        with self.lock:
            row=self.db.execute('SELECT payload FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
        return json.loads(row[0]) if row else None
    def export(self):
        with self.lock:
            return {'snapshots':[json.loads(x[0]) for x in self.db.execute('SELECT payload FROM snapshots ORDER BY id')], 'events':[json.loads(x[0]) for x in self.db.execute('SELECT payload FROM events ORDER BY ts,event_id')], 'messages':[json.loads(x[0]) for x in self.db.execute('SELECT payload FROM messages ORDER BY ts,message_id')]}
