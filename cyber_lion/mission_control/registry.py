class AdapterRegistry:
 def __init__(self,adapters=()): self.adapters={a.adapter_id:a for a in adapters}
 def ids(self): return sorted(self.adapters)
 def discover(self):
  out=[]
  for a in self.adapters.values():
   try: out.extend(a.discover_runs())
   except Exception: continue
  return out
