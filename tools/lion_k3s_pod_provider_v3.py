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
    return payload

v2.transformed_manifest=transformed_manifest_v3

def main(): return v2.main()
if __name__=='__main__': raise SystemExit(main())
