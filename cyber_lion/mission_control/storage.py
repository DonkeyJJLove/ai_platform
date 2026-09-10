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
 def index_run(self,r):
  raw=json.dumps(r,sort_keys=True,separators=(',',':'));rid=r['run_id']
  with self.lock:
   self.db.execute('INSERT OR REPLACE INTO runs VALUES(?,?)',(rid,raw))
   for table in ('metrics','participants','artifacts','receipts'):self.db.execute(f'DELETE FROM {table} WHERE run_id=?',(rid,))
   for name,value in (r.get('metrics') or {}).items():self.db.execute('INSERT INTO metrics(run_id,name,payload) VALUES(?,?,?)',(rid,name,json.dumps(value,sort_keys=True,separators=(',',':'))))
   participants=r.get('participants') or []
   if isinstance(participants,dict):participants=[{'id':k,'value':v} for k,v in participants.items()]
   for p in participants:self.db.execute('INSERT INTO participants(run_id,payload) VALUES(?,?)',(rid,json.dumps(p,sort_keys=True,separators=(',',':'))))
   for a in r.get('artifacts') or []:self.db.execute('INSERT INTO artifacts(run_id,path,sha256,payload) VALUES(?,?,?,?)',(rid,a.get('path'),a.get('sha256'),json.dumps(a,sort_keys=True,separators=(',',':'))))
   for q in r.get('receipts') or []:self.db.execute('INSERT INTO receipts(run_id,payload) VALUES(?,?)',(rid,json.dumps(q,sort_keys=True,separators=(',',':'))))
   self.db.commit()
 def upsert_run(self,r):self.index_run(r)
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
 def export_run(self,rid):
  r=self.run(rid)
  if not r:return None
  return {'run':r,'events':self.events(rid),'metrics':self.metrics(rid),'participants':self.table_payloads('participants',rid),'artifacts':self.artifacts(rid),'receipts':self.table_payloads('receipts',rid)}
