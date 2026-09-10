from __future__ import annotations
import json,sqlite3,threading
from pathlib import Path
SCHEMA='''CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,ts REAL NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,name TEXT,payload TEXT);
CREATE TABLE IF NOT EXISTS participants(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,payload TEXT);
CREATE TABLE IF NOT EXISTS artifacts(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,path TEXT,sha256 TEXT,payload TEXT);
CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,payload TEXT);
CREATE TABLE IF NOT EXISTS adapter_state(adapter_id TEXT PRIMARY KEY,payload TEXT NOT NULL);'''
class Store:
 def __init__(self,path):
  self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock()
  self.db=sqlite3.connect(self.path,check_same_thread=False); self.db.executescript(SCHEMA); self.db.execute('PRAGMA journal_mode=WAL'); self.db.commit()
 def upsert_run(self,r):
  with self.lock:self.db.execute('INSERT OR REPLACE INTO runs VALUES(?,?)',(r['run_id'],json.dumps(r,sort_keys=True,separators=(',',':'))));self.db.commit()
 def add_event(self,e):
  with self.lock:self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?)',(e['event_id'],e['run_id'],float(e['timestamp']),json.dumps(e,sort_keys=True,separators=(',',':'))));self.db.commit()
 def runs(self): return [json.loads(x[0]) for x in self.db.execute('SELECT payload FROM runs ORDER BY run_id')]
 def run(self,rid):
  x=self.db.execute('SELECT payload FROM runs WHERE run_id=?',(rid,)).fetchone(); return json.loads(x[0]) if x else None
 def events(self,rid): return [json.loads(x[0]) for x in self.db.execute('SELECT payload FROM events WHERE run_id=? ORDER BY ts,event_id',(rid,))]
 def table_payloads(self,table,rid):
  if table not in {'participants','receipts'}: raise ValueError('bad table')
  return [json.loads(x[0]) for x in self.db.execute(f'SELECT payload FROM {table} WHERE run_id=? ORDER BY id',(rid,))]
 def metrics(self,rid): return {n:json.loads(p) for n,p in self.db.execute('SELECT name,payload FROM metrics WHERE run_id=? ORDER BY id',(rid,))}
 def artifacts(self,rid): return [json.loads(x[0]) for x in self.db.execute('SELECT payload FROM artifacts WHERE run_id=? ORDER BY id',(rid,))]
