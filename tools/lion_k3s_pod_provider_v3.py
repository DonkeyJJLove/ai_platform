#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
V2_PATH=HERE/'lion_k3s_pod_provider_v2.py'

def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError('module-load-failed:'+str(path))
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

v2=_load('lion_k3s_pod_provider_v2_overlay',V2_PATH)
_base=v2.transformed_manifest

def transformed_manifest_v3():
    payload=_base()
    cfg=next(d for d in payload.get('documents',[]) if d.get('kind')=='ConfigMap' and (d.get('metadata') or {}).get('name')=='vkt-runtime')
    src=(cfg.get('data') or {}).get('drone.py','')
    old="router=os.environ.get('VKT_ROUTER','http://vkt-fleet-router:8080')"
    new="router='http://'+os.environ.get('VKT_FLEET_ROUTER_SERVICE_HOST','10.43.0.1')+':'+os.environ.get('VKT_FLEET_ROUTER_SERVICE_PORT','8080')"
    if old not in src and new not in src: raise RuntimeError('drone-router-source-contract-missing')
    cfg['data']['drone.py']=src.replace(old,new)
    runtime_sha=hashlib.sha256(json.dumps(cfg['data'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for doc in payload.get('documents',[]):
        if doc.get('kind') in {'Deployment','StatefulSet'}:
            meta=doc.setdefault('spec',{}).setdefault('template',{}).setdefault('metadata',{})
            meta.setdefault('annotations',{})['vkt-runtime-sha256']=runtime_sha
    # Router serves concurrent heartbeat/task traffic from 384 drones.
    for doc in payload.get('documents',[]):
        if doc.get('kind')=='Deployment' and (doc.get('metadata') or {}).get('name')=='vkt-fleet-router':
            c=doc['spec']['template']['spec']['containers'][0]
            c['resources']={'requests':{'cpu':'50m','memory':'64Mi'},'limits':{'cpu':'1000m','memory':'512Mi'}}
    return payload

v2.transformed_manifest=transformed_manifest_v3
_original_install=v2.install_into_core

def install_into_core_v3(core):
    _original_install(core)
    base_materialize=core.materialize
    def materialize_v3():
        desired=transformed_manifest_v3()
        workloads=[d for d in desired.get('documents',[]) if d.get('kind')=='StatefulSet']
        hashes={d['spec']['template']['metadata']['annotations']['vkt-runtime-sha256'] for d in workloads}
        if len(hashes)!=1: raise RuntimeError('runtime-hash-cardinality')
        expected_hash=next(iter(hashes))
        result=base_materialize()
        data=json.loads(core.kubectl(['get','pods','-n',core.NAMESPACE,'-l','component=drone','-o','json'],timeout=30).stdout)
        stale=[]
        for item in data.get('items',[]) or []:
            meta=item.get('metadata') or {}; name=str(meta.get('name') or '')
            ann=meta.get('annotations') or {}; actual=ann.get('vkt-runtime-sha256')
            parts=name.rsplit('-',1)
            if actual==expected_hash: continue
            if len(parts)!=2 or parts[0] not in {'tiger-drone','spectra-drone','lion-drone'} or not parts[1].isdigit():
                raise RuntimeError('runtime-rollout-name-denied:'+name)
            stale.append(name)
        stale=sorted(set(stale))
        if len(stale)>384: raise RuntimeError('runtime-rollout-cardinality:'+str(len(stale)))
        for name in stale:
            core.kubectl(['delete','pod','-n',core.NAMESPACE,name,'--wait=false'],timeout=30)
        result['runtime_hash_expected']=expected_hash
        result['runtime_mismatch_recycled']=stale
        result['runtime_mismatch_recycled_count']=len(stale)
        return result
    core.materialize=materialize_v3

v2.install_into_core=install_into_core_v3

def main(): return v2.main()
if __name__=='__main__': raise SystemExit(main())
