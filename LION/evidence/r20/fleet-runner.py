#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, sys
from pathlib import Path
from datetime import datetime, timezone

SRC=Path("/src")
EVID=Path("/evidence")
OUT=Path("/out")

def digest_bytes(b): return hashlib.sha256(b).hexdigest()
def read_rel(rel, base=SRC, limit=2_000_000):
    p=(base/rel).resolve()
    if base.resolve() not in p.parents and p != base.resolve(): raise ValueError("path escape")
    b=p.read_bytes()
    if len(b)>limit: raise ValueError("file too large")
    return p,b,b.decode("utf-8","replace")
def evidence():
    return json.loads((EVID/"currentness.json").read_text(encoding="utf-8"))
def result(role, status, finding, ev, extra=None):
    row={"role_id":role["role_id"],"title":role["title"],"task":role["task"],"status":status,
         "finding":finding,"evidence":ev,"completed_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
    if extra: row.update(extra)
    return row

def do(role):
    t=role["task"]; p=role.get("params") or {}
    try:
      if t=="contains":
        path,b,s=read_rel(p["path"]); needles=p["needles"]; missing=[x for x in needles if x not in s]
        return result(role,"PASS" if not missing else "FAIL",f"missing={missing}" if missing else "all required markers present",
                      [f"sha256:{digest_bytes(b)}",p["path"]],{"missing":missing})
      if t=="regex":
        path,b,s=read_rel(p["path"]); n=len(re.findall(p["pattern"],s,re.M))
        lo=int(p.get("min",1)); ok=n>=lo
        return result(role,"PASS" if ok else "FAIL",f"matches={n}, required>={lo}",[f"sha256:{digest_bytes(b)}",p["path"]],{"matches":n})
      if t=="hash":
        path,b,s=read_rel(p["path"]); got=digest_bytes(b); want=p.get("expected"); ok=(not want or got==want)
        return result(role,"PASS" if ok else "FAIL",f"sha256={got}",[p["path"]],{"sha256":got,"expected":want})
      if t=="json":
        data=evidence(); cur=data
        for key in p["path"].split("."): cur=cur[key]
        expected=p.get("expected","__ANY__"); ok=(expected=="__ANY__" or cur==expected)
        return result(role,"PASS" if ok else "FAIL",f"{p['path']}={cur!r}",["currentness.json"],{"value":cur,"expected":expected})
      if t=="json_present":
        data=evidence(); cur=data
        for key in p["path"].split("."): cur=cur[key]
        ok=cur is not None and cur!=""
        return result(role,"PASS" if ok else "FAIL",f"{p['path']} present={ok}",["currentness.json"])
      if t=="json_absent":
        data=evidence(); cur=data
        for key in p["path"].split("."): cur=cur.get(key) if isinstance(cur,dict) else None
        ok=cur in (None,False,"",[])
        return result(role,"PASS" if ok else "FAIL",f"{p['path']} absent={ok}",["currentness.json"])
      if t=="block":
        data=evidence(); why=p["reason"]; return result(role,"BLOCKED",why,["currentness.json"],{"blocker":why})
      if t=="py_compile":
        path,b,s=read_rel(p["path"]); compile(s,str(path),"exec")
        return result(role,"PASS","python source compiles", [f"sha256:{digest_bytes(b)}",p["path"]])
      if t=="sqlite_schema":
        db=(EVID/p["db"]).resolve()
        c=sqlite3.connect(f"file:{db}?mode=ro",uri=True)
        names=sorted(x[0] for x in c.execute("select name from sqlite_master where type='table'").fetchall()); c.close()
        required=p["tables"]; missing=[x for x in required if x not in names]
        return result(role,"PASS" if not missing else "FAIL",f"tables={len(names)} missing={missing}",[p["db"]],{"tables":names})
      if t=="compare_text":
        p1,b1,s1=read_rel(p["path1"]); p2,b2,s2=read_rel(p["path2"],EVID)
        ok=p["needle"] in s1 and p["needle"] in s2
        return result(role,"PASS" if ok else "FAIL",f"needle present in source+evidence={ok}",
                      [p["path1"],p["path2"],f"sha256:{digest_bytes(b1)}",f"sha256:{digest_bytes(b2)}"])
      raise ValueError("unknown closed task")
    except Exception as exc:
      return result(role,"FAIL",f"{type(exc).__name__}: {str(exc)[:300]}",[])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--spec",required=True); a=ap.parse_args()
    spec=json.loads(Path(a.spec).read_text(encoding="utf-8"))
    rows=[do(r) for r in spec["roles"]]
    payload={"schema":"lion.r20.worker-results/v1","task_id":spec["task_id"],"worker_id":spec["worker_id"],
             "started_at":spec["started_at"],"completed_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
             "roles":rows}
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    payload["result_digest"]=digest_bytes(raw)
    print("LION_RESULT="+json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":")))
    print(json.dumps({"worker_id":spec["worker_id"],"roles":len(rows),"pass":sum(r["status"]=="PASS" for r in rows),
                      "blocked":sum(r["status"]=="BLOCKED" for r in rows),"fail":sum(r["status"]=="FAIL" for r in rows),
                      "result_digest":payload["result_digest"]},sort_keys=True))
    return 0 if not any(r["status"]=="FAIL" for r in rows) else 2
if __name__=="__main__": raise SystemExit(main())
