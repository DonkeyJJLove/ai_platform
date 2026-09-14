from hashlib import sha256
from pathlib import Path
import os
class RepositoryReader:
    def __init__(self,root,git_provider,content_provider=None):
        self.root=Path(root).resolve(strict=True)
        if not callable(git_provider):raise ValueError('explicit read-only git provider required')
        if content_provider is not None and not callable(content_provider):raise ValueError('content provider')
        self.git_provider=git_provider;self.content_provider=content_provider
    def _path(self,rel):
        if not isinstance(rel,str) or not rel or '\x00' in rel:raise ValueError('path denied')
        candidate=(self.root/rel).resolve(strict=False)
        if self.root not in candidate.parents:raise ValueError('path denied')
        parts=candidate.relative_to(self.root).parts
        if any(x in {'.git','.venv','node_modules','.secret','.credentials'} for x in parts) or candidate.name=='.env':raise ValueError('path denied')
        try:return candidate.resolve(strict=True)
        except FileNotFoundError as e:raise ValueError('path unavailable') from e
    def read_file(self,rel):
        if self.content_provider is not None:return self.content_provider('read_file',{'path':rel})
        p=self._path(rel);b=p.read_bytes()
        if len(b)>262144:raise ValueError('file too large')
        return {'path':str(p.relative_to(self.root)).replace('\\','/'),'sha256':sha256(b).hexdigest(),'text':b.decode('utf-8')}
    def _git(self,operation):
        v=self.git_provider(operation,{'repository_root':str(self.root)})
        if operation=='head_tree':
            if type(v) is not dict or set(v)!={'head','tree'}:raise ValueError('git provider result')
        elif operation=='status':
            if type(v) is not list:raise ValueError('git provider result')
        return v
    def head_tree(self):return self._git('head_tree')
    def status(self):return self._git('status')
    def search(self,q,limit=20):
        if self.content_provider is not None:return self.content_provider('search',{'query':q,'limit':limit})
        out=[]
        for base,dirs,files in os.walk(self.root):
            dirs[:]=[d for d in dirs if d not in {'.git','.venv','node_modules','__pycache__'}]
            for name in files:
                p=Path(base)/name
                if p.suffix.lower() not in {'.py','.md','.json','.yaml','.yml','.txt','.toml'}:continue
                try:t=p.read_text(encoding='utf-8')
                except (OSError,UnicodeError):continue
                i=t.lower().find(q.lower())
                if i>=0:
                    out.append({'path':str(p.relative_to(self.root)).replace('\\','/'),'snippet':t[max(0,i-120):i+700]})
                    if len(out)>=limit:return out
        return out
