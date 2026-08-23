"""Restart-durable Enterprise Graph. Graph state is evidence, never execution authority."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime,timezone
from hashlib import sha256
import json,sqlite3
from pathlib import Path
from collections import deque
from cyber_lion.contracts.enterprise_graph import EnterpriseGraphError,EnterpriseGraphProjection,GraphEdge,GraphNode,GraphPath,canonical_json

_ZERO="0"*64
class EnterpriseGraphStateError(RuntimeError):pass

def _now(clock):
    value=clock()
    if not isinstance(value,datetime) or value.tzinfo is None:raise EnterpriseGraphStateError("trusted clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()

def _node_raw(n:GraphNode):
    n.validate();d=asdict(n);d["provenance_refs"]=list(n.provenance_refs);return d

def _edge_raw(e:GraphEdge):
    e.validate();d=asdict(e);d["provenance_refs"]=list(e.provenance_refs);return d

def _node_from(raw:str):
    try:d=json.loads(raw);d["provenance_refs"]=tuple(d.get("provenance_refs",()))
    except Exception as exc:raise EnterpriseGraphStateError("stored node invalid") from exc
    try:return GraphNode(**d).validate()
    except Exception as exc:raise EnterpriseGraphStateError("stored node invalid") from exc

def _edge_from(raw:str):
    try:d=json.loads(raw);d["provenance_refs"]=tuple(d.get("provenance_refs",()))
    except Exception as exc:raise EnterpriseGraphStateError("stored edge invalid") from exc
    try:return GraphEdge(**d).validate()
    except Exception as exc:raise EnterpriseGraphStateError("stored edge invalid") from exc

def _event_digest(previous:str,event_type:str,payload:dict,observed_at:str)->str:
    return sha256(canonical_json({"previous_digest":previous,"event_type":event_type,"payload":payload,"observed_at":observed_at})).hexdigest()

class EnterpriseGraphStore:
    def __init__(self,db_path,*,graph_id,clock):
        if not graph_id:raise EnterpriseGraphStateError("graph_id required")
        self.graph_id=graph_id;self.clock=clock;self.db_path=str(Path(db_path));self.c=sqlite3.connect(self.db_path,isolation_level=None);self.c.row_factory=sqlite3.Row
        try:
            self.c.execute("PRAGMA foreign_keys=ON");self.c.execute("PRAGMA journal_mode=WAL");self.c.execute("PRAGMA synchronous=FULL")
            self._schema();self._bind();self.verify_event_chain();self.verify_consistency()
        except Exception:self.c.close();raise
    def close(self):self.c.close()
    def _schema(self):
        self.c.executescript("""
CREATE TABLE IF NOT EXISTS enterprise_graph_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),graph_id TEXT NOT NULL,revision INTEGER NOT NULL,event_head TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_graph_node(node_id TEXT PRIMARY KEY,node_type TEXT NOT NULL,version TEXT NOT NULL,node_digest TEXT NOT NULL,node_json TEXT NOT NULL,registered_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_graph_edge(edge_id TEXT PRIMARY KEY,plane TEXT NOT NULL,edge_type TEXT NOT NULL,source_id TEXT NOT NULL,target_id TEXT NOT NULL,edge_digest TEXT NOT NULL,edge_json TEXT NOT NULL,registered_at TEXT NOT NULL,FOREIGN KEY(source_id) REFERENCES enterprise_graph_node(node_id),FOREIGN KEY(target_id) REFERENCES enterprise_graph_node(node_id));
CREATE TABLE IF NOT EXISTS enterprise_graph_operation(operation_id TEXT PRIMARY KEY,operation_digest TEXT NOT NULL,result_json TEXT NOT NULL,result_digest TEXT NOT NULL,observed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_graph_event(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,event_type TEXT NOT NULL,payload_json TEXT NOT NULL,previous_digest TEXT NOT NULL,event_digest TEXT UNIQUE NOT NULL,observed_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS graph_node_no_update BEFORE UPDATE ON enterprise_graph_node BEGIN SELECT RAISE(ABORT,'graph node append-only');END;
CREATE TRIGGER IF NOT EXISTS graph_node_no_delete BEFORE DELETE ON enterprise_graph_node BEGIN SELECT RAISE(ABORT,'graph node append-only');END;
CREATE TRIGGER IF NOT EXISTS graph_edge_no_update BEFORE UPDATE ON enterprise_graph_edge BEGIN SELECT RAISE(ABORT,'graph edge append-only');END;
CREATE TRIGGER IF NOT EXISTS graph_edge_no_delete BEFORE DELETE ON enterprise_graph_edge BEGIN SELECT RAISE(ABORT,'graph edge append-only');END;
CREATE TRIGGER IF NOT EXISTS graph_op_no_update BEFORE UPDATE ON enterprise_graph_operation BEGIN SELECT RAISE(ABORT,'graph operation append-only');END;
CREATE TRIGGER IF NOT EXISTS graph_op_no_delete BEFORE DELETE ON enterprise_graph_operation BEGIN SELECT RAISE(ABORT,'graph operation append-only');END;
CREATE TRIGGER IF NOT EXISTS graph_event_no_update BEFORE UPDATE ON enterprise_graph_event BEGIN SELECT RAISE(ABORT,'graph event append-only');END;
CREATE TRIGGER IF NOT EXISTS graph_event_no_delete BEFORE DELETE ON enterprise_graph_event BEGIN SELECT RAISE(ABORT,'graph event append-only');END;
""")
    def _bind(self):
        row=self.c.execute("SELECT graph_id FROM enterprise_graph_meta WHERE singleton=1").fetchone()
        if row is None:self.c.execute("INSERT INTO enterprise_graph_meta VALUES(1,?,?,?)",(self.graph_id,0,_ZERO))
        elif row[0]!=self.graph_id:raise EnterpriseGraphStateError("graph substitution denied")
    def _tx(self,fn):
        try:self.c.execute("BEGIN IMMEDIATE");out=fn();self.c.execute("COMMIT");return out
        except Exception:
            if self.c.in_transaction:self.c.execute("ROLLBACK")
            raise
    def _append(self,event_type,payload,at):
        prev=self.c.execute("SELECT event_head FROM enterprise_graph_meta WHERE singleton=1").fetchone()[0]
        dg=_event_digest(prev,event_type,payload,at)
        self.c.execute("INSERT INTO enterprise_graph_event(event_id,event_type,payload_json,previous_digest,event_digest,observed_at) VALUES(?,?,?,?,?,?)",(dg,event_type,canonical_json(payload).decode(),prev,dg,at))
        self.c.execute("UPDATE enterprise_graph_meta SET revision=revision+1,event_head=? WHERE singleton=1",(dg,))
    def _cached(self,operation_id,payload):
        if not operation_id:raise EnterpriseGraphStateError("operation_id required")
        od=sha256(canonical_json(payload)).hexdigest();row=self.c.execute("SELECT operation_digest,result_json,result_digest FROM enterprise_graph_operation WHERE operation_id=?",(operation_id,)).fetchone()
        if row is None:return od,None
        if row[0]!=od or sha256(row[1].encode()).hexdigest()!=row[2]:raise EnterpriseGraphStateError("operation replay substitution/corruption denied")
        return od,json.loads(row[1])
    def _save(self,operation_id,operation_digest,result,at):
        raw=json.dumps(result,sort_keys=True,separators=(",",":"));self.c.execute("INSERT INTO enterprise_graph_operation VALUES(?,?,?,?,?)",(operation_id,operation_digest,raw,sha256(raw.encode()).hexdigest(),at))
    def add_node(self,node:GraphNode,*,operation_id,evidence_refs=()):
        node.validate();payload={"kind":"add_node","node":_node_raw(node),"evidence_refs":list(evidence_refs)}
        def work():
            od,cached=self._cached(operation_id,payload)
            if cached:return _node_from(canonical_json(cached).decode())
            existing=self.c.execute("SELECT node_digest,node_json FROM enterprise_graph_node WHERE node_id=?",(node.node_id,)).fetchone()
            if existing:
                if existing[0]!=node.digest():raise EnterpriseGraphStateError("node id payload substitution denied")
                raise EnterpriseGraphStateError("node already exists under different operation")
            at=_now(self.clock);raw=canonical_json(_node_raw(node)).decode();self.c.execute("INSERT INTO enterprise_graph_node VALUES(?,?,?,?,?,?)",(node.node_id,node.node_type,node.version,node.digest(),raw,at));self._append("NODE_ADDED",payload,at);self._save(operation_id,od,_node_raw(node),at);return node
        return self._tx(work)
    def add_edge(self,edge:GraphEdge,*,operation_id,evidence_refs=()):
        edge.validate();payload={"kind":"add_edge","edge":_edge_raw(edge),"evidence_refs":list(evidence_refs)}
        def work():
            od,cached=self._cached(operation_id,payload)
            if cached:return _edge_from(canonical_json(cached).decode())
            if edge.source_id==edge.target_id:raise EnterpriseGraphStateError("self edge denied")
            nodes={r[0] for r in self.c.execute("SELECT node_id FROM enterprise_graph_node WHERE node_id IN (?,?)",(edge.source_id,edge.target_id))}
            if nodes!={edge.source_id,edge.target_id}:raise EnterpriseGraphStateError("dangling edge denied")
            existing=self.c.execute("SELECT edge_digest FROM enterprise_graph_edge WHERE edge_id=?",(edge.edge_id,)).fetchone()
            if existing:
                if existing[0]!=edge.digest():raise EnterpriseGraphStateError("edge id payload substitution denied")
                raise EnterpriseGraphStateError("edge already exists under different operation")
            at=_now(self.clock);raw=canonical_json(_edge_raw(edge)).decode();self.c.execute("INSERT INTO enterprise_graph_edge VALUES(?,?,?,?,?,?,?,?)",(edge.edge_id,edge.plane,edge.edge_type,edge.source_id,edge.target_id,edge.digest(),raw,at));self._append("EDGE_ADDED",payload,at);self._save(operation_id,od,_edge_raw(edge),at);return edge
        return self._tx(work)
    def projection(self):
        meta=self.c.execute("SELECT graph_id,revision,event_head FROM enterprise_graph_meta WHERE singleton=1").fetchone()
        nodes=tuple(_node_from(r[0]) for r in self.c.execute("SELECT node_json FROM enterprise_graph_node ORDER BY node_type,node_id,version,node_digest"))
        edges=tuple(_edge_from(r[0]) for r in self.c.execute("SELECT edge_json FROM enterprise_graph_edge ORDER BY plane,edge_type,source_id,target_id,edge_id"))
        logical={"graph_id":meta[0],"nodes":[_node_raw(n) for n in nodes],"edges":[_edge_raw(e) for e in edges]}
        dg=sha256(canonical_json(logical)).hexdigest();return EnterpriseGraphProjection(meta[0],meta[1],meta[2],nodes,edges,dg).verify_digest()
    def find_path(self,source_id,target_id,*,plane):
        if plane not in {"DATA_PROVENANCE","AUTHORITY_REFERENCE"}:raise EnterpriseGraphStateError("explicit valid plane required")
        if not self.c.execute("SELECT 1 FROM enterprise_graph_node WHERE node_id=?",(source_id,)).fetchone() or not self.c.execute("SELECT 1 FROM enterprise_graph_node WHERE node_id=?",(target_id,)).fetchone():raise EnterpriseGraphStateError("path endpoint unknown")
        if source_id==target_id:return GraphPath(plane,(source_id,),()).validate()
        adj={}
        for r in self.c.execute("SELECT edge_id,source_id,target_id FROM enterprise_graph_edge WHERE plane=? ORDER BY edge_type,source_id,target_id,edge_id",(plane,)):
            adj.setdefault(r[1],[]).append((r[2],r[0]))
        q=deque([(source_id,(source_id,),())]);seen={source_id}
        while q:
            cur,nodes,edges=q.popleft()
            for nxt,eid in adj.get(cur,()):
                if nxt in seen:continue
                nn=nodes+(nxt,);ee=edges+(eid,)
                if nxt==target_id:return GraphPath(plane,nn,ee).validate()
                seen.add(nxt);q.append((nxt,nn,ee))
        raise EnterpriseGraphStateError("path not found")
    def authority_reference_path(self,source_id,target_id):
        return self.find_path(source_id,target_id,plane="AUTHORITY_REFERENCE")
    def verify_event_chain(self):
        prev=_ZERO
        for r in self.c.execute("SELECT * FROM enterprise_graph_event ORDER BY seq"):
            try:payload=json.loads(r["payload_json"])
            except Exception as exc:raise EnterpriseGraphStateError("event corruption") from exc
            dg=_event_digest(prev,r["event_type"],payload,r["observed_at"])
            if r["previous_digest"]!=prev or r["event_digest"]!=dg or r["event_id"]!=dg:raise EnterpriseGraphStateError("event chain corruption")
            prev=dg
        if self.c.execute("SELECT event_head FROM enterprise_graph_meta WHERE singleton=1").fetchone()[0]!=prev:raise EnterpriseGraphStateError("event head mismatch")
        return prev
    def verify_consistency(self):
        for r in self.c.execute("SELECT node_digest,node_json FROM enterprise_graph_node"):
            n=_node_from(r[1])
            if r[0]!=n.digest():raise EnterpriseGraphStateError("node corruption")
        known={r[0] for r in self.c.execute("SELECT node_id FROM enterprise_graph_node")}
        for r in self.c.execute("SELECT edge_digest,edge_json,source_id,target_id FROM enterprise_graph_edge"):
            e=_edge_from(r[1])
            if r[0]!=e.digest():raise EnterpriseGraphStateError("edge corruption")
            if r[2] not in known or r[3] not in known:raise EnterpriseGraphStateError("dangling edge corruption")
        return True
