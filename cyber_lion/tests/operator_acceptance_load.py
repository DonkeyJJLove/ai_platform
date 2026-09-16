#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,hashlib,json,math,os,sqlite3,statistics,tempfile,threading,time,uuid
from pathlib import Path
from cyber_lion.mission_control import operator_control

DURATION=600.0;RATE=100.0;BURST_DURATION=30.0;BURST_RATE=1000.0;COMMANDS=1000;CLIENTS=64

def utc():
    from datetime import datetime,timezone
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def percentile(xs,p):
    ys=sorted(xs);return ys[min(len(ys)-1,max(0,math.ceil(p*len(ys))-1))] if ys else None

def connect(path):
    c=sqlite3.connect(path,timeout=3,check_same_thread=False);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA busy_timeout=2500');return c

def setup(path):
    c=connect(path);c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,updated_at TEXT)');c.execute("INSERT INTO missions VALUES('LOAD-M','RUNNING',?)",(utc(),));operator_control.migrate(c,utc);operator_control.ensure_primary_operator(c,utc);c.close()

def event_writer(path,duration,rate,label,stats):
    c=connect(path);period=1.0/rate;deadline=time.monotonic()+duration;next_at=time.monotonic();n=0;errors=0;lat=[];fatal=None
    while time.monotonic()<deadline:
        nowm=time.monotonic()
        if nowm<next_at:time.sleep(min(next_at-nowm,.01));continue
        payload={'source':label,'seq':n};raw=json.dumps(payload,separators=(',',':'));t=time.perf_counter()
        try:
            c.execute("INSERT INTO operator_events(mission_id,command_id,event_type,payload_json,payload_digest,observed_at) VALUES('LOAD-M',NULL,?,?,?,?)",(label,raw,hashlib.sha256(raw.encode()).hexdigest(),utc()));c.commit();lat.append(time.perf_counter()-t);n+=1
        except sqlite3.OperationalError as exc:errors+=1;fatal=f'{type(exc).__name__}:{exc}'
        next_at+=period
        if next_at<time.monotonic()-1:next_at=time.monotonic()
    c.close();stats.update(count=n,errors=errors,latencies=lat,fatal=fatal)

def one_command(path,i):
    c=connect(path);value={'command_id':f'load-{i:04d}','mission_id':'LOAD-M','action':'REQUEST_STATUS','target':'mission:LOAD-M','payload':{}};t=time.perf_counter()
    try:out=operator_control.apply_command(c,value,utc);return time.perf_counter()-t,None,out['admission_state']
    except Exception as e:return time.perf_counter()-t,type(e).__name__+':'+str(e),None
    finally:c.close()

def main():
    root=Path(tempfile.mkdtemp(prefix='lion-operator-load-'));db=root/'load.db';setup(db)
    normal={};thread=threading.Thread(target=event_writer,args=(db,DURATION,RATE,'TELEMETRY',normal),daemon=True);start=time.perf_counter();thread.start();time.sleep(.5)
    lat=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=CLIENTS) as pool:
        for elapsed,error,state in pool.map(lambda i:one_command(db,i),range(COMMANDS)):
            lat.append(elapsed)
            if error:errors.append(error)
    # High-priority containment admission while telemetry is still active.
    c=connect(db);state=operator_control.control_state(c,'LOAD-M',utc);stop={'command_id':'priority-stop','mission_id':'LOAD-M','action':'STOP_SCOPE','target':'mission:LOAD-M','payload':{},'expected_revision':state['control_epoch']};t=time.perf_counter();stopout=operator_control.apply_command(c,stop,utc);stop_latency=time.perf_counter()-t;c.close()
    thread.join()
    burst={};event_writer(db,BURST_DURATION,BURST_RATE,'BURST',burst)
    c=connect(db);counts={r['event_type']:r['n'] for r in c.execute('SELECT event_type,COUNT(*) n FROM operator_events GROUP BY event_type')};command_count=c.execute('SELECT COUNT(*) FROM operator_commands').fetchone()[0];receipt_count=c.execute('SELECT COUNT(*) FROM operator_command_receipts').fetchone()[0];integrity=c.execute('PRAGMA integrity_check').fetchone()[0];c.close()
    report={'schema':'lion.operator-load-acceptance/v1','clients':CLIENTS,'command_attempts':COMMANDS,'command_errors':len(errors),'command_error_samples':errors[:10],
            'command_latency_ms':{'p50':round(percentile(lat,.50)*1000,3),'p95':round(percentile(lat,.95)*1000,3),'p99':round(percentile(lat,.99)*1000,3),'max':round(max(lat)*1000,3)},
            'stop_latency_ms':round(stop_latency*1000,3),'stop_state':stopout['observation_state'],
            'telemetry':{'requested_rate':RATE,'duration_s':DURATION,'count':normal.get('count'),'errors':normal.get('errors'),'p95_write_ms':(round(percentile(normal.get('latencies',[]),.95)*1000,3) if normal.get('latencies') else None),'fatal':normal.get('fatal')},
            'burst':{'requested_rate':BURST_RATE,'duration_s':BURST_DURATION,'count':burst.get('count'),'errors':burst.get('errors'),'p95_write_ms':(round(percentile(burst.get('latencies',[]),.95)*1000,3) if burst.get('latencies') else None),'fatal':burst.get('fatal')},
            'ledger':{'commands':command_count,'receipts':receipt_count,'events_by_type':counts,'integrity':integrity},'wall_s':round(time.perf_counter()-start,3)}
    report['pass']=(len(errors)==0 and normal.get('errors')==0 and burst.get('errors')==0 and normal.get('count',0)>0 and burst.get('count',0)>0 and command_count==COMMANDS+1 and receipt_count==COMMANDS+1 and integrity=='ok' and stop_latency<=2.0)
    out=Path('/opt/lion/operator-intervention-r1/operator-load-result.json');out.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
