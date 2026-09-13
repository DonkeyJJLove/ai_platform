from dataclasses import dataclass,asdict
from hashlib import sha256
import json,re,zipfile
from pathlib import Path
BEGIN=re.compile(r"^LION_RECORD_BEGIN:\s*(\S+)",re.M);META=re.compile(r"^LION_RECORD_META:\s*(\{.*\})\s*$",re.M);TOK=re.compile(r"[\w.-]+")
@dataclass(frozen=True)
class RagHit:
    source_id:str;virtual_path:str;source_sha256:str;release_id:str;currentness_class:str;authority_effect:str;score:int;snippet:str
    def as_dict(self):return asdict(self)
class RagIndex:
    def __init__(self,path,expected_sha256,release_id):
        p=Path(path).resolve(strict=True);blob=p.read_bytes();actual=sha256(blob).hexdigest()
        if actual!=expected_sha256:raise ValueError("RAG ZIP identity mismatch")
        self.sha256=actual;self.release_id=release_id;self.rows=[];total=0
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if name.endswith('/') or not name.lower().endswith(('.md','.txt','.json','.yaml','.yml')):continue
                b=z.read(name);total+=len(b)
                if total>32000000:raise ValueError("RAG expanded size limit")
                s=b.decode('utf-8');starts=list(BEGIN.finditer(s))
                if not starts:self.rows.append(("FILE::"+name,name,sha256(b).hexdigest(),"VERSIONED_PACKAGE","NONE",s));continue
                for i,m in enumerate(starts):
                    q=s[m.start():(starts[i+1].start() if i+1<len(starts) else len(s))];mm=META.search(q)
                    if not mm:continue
                    meta=json.loads(mm.group(1));self.rows.append((str(meta.get('source_id',m.group(1))),str(meta.get('virtual_path',name)),str(meta.get('sha256',sha256(q.encode()).hexdigest())),str(meta.get('currentness','UNKNOWN')),str(meta.get('authority_effect','NONE')),q))
        if not self.rows:raise ValueError("empty RAG")
    def search(self,query,limit=5):
        if not isinstance(query,str) or not query.strip() or type(limit) is not int or not 1<=limit<=10:raise ValueError("query")
        terms=[x.lower() for x in TOK.findall(query) if len(x)>1][:24];out=[]
        for sid,vp,sh,cur,auth,text in self.rows:
            low=(vp+' '+text).lower();score=sum(low.count(t) for t in terms)+(20 if query.lower() in low else 0)
            if score:out.append(RagHit(sid,vp,sh,self.release_id,cur,auth,score,text[:1200]))
        return tuple(sorted(out,key=lambda x:(-x.score,x.source_id))[:limit])
