"""Repository entrypoint for the deny-only observer and operator qualification."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0,str(REPO))

def main(argv=None):
    from cyber_lion.mission_control.edge_support import EdgeRejected,canonical,digest,object_bytes,read_regular,write_new
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    p = sub.add_parser('init');p.add_argument('--home',required=True);p.add_argument('--host-id',required=True)
    p = sub.add_parser('watch');p.add_argument('--home',required=True);p.add_argument('--seconds',type=float)
    p = sub.add_parser('state');p.add_argument('--home',required=True)
    p = sub.add_parser('demo');p.add_argument('--output',required=True);p.add_argument('--host-id',default='MOON');p.add_argument('--model-endpoint')
    p = sub.add_parser('r24-pilot');p.add_argument('--output',required=True);p.add_argument('--docker-exe',required=True);p.add_argument('--home',required=True);p.add_argument('--local-model',action='store_true')
    p = sub.add_parser('export-audit');p.add_argument('--home',required=True);p.add_argument('--output',required=True)
    p = sub.add_parser('verify-export');p.add_argument('--input',required=True);p.add_argument('--public-key',required=True);p.add_argument('--expected-head',required=True)
    p = sub.add_parser('receive');p.add_argument('--bundle',required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--binding',required=True);p.add_argument('--private-parent',required=True)
    a = parser.parse_args(argv)
    try:
        if a.command == 'init':
            from cyber_lion.enterprise.edge_yoke.observer import initialize
            result = initialize(a.home,a.host_id)
        elif a.command == 'watch':
            from cyber_lion.enterprise.edge_yoke.observer import watch
            print('Observer in foreground; State reads the signed snapshot. Ctrl+C stops only this observer.',file=sys.stderr,flush=True)
            result = watch(a.home,seconds=a.seconds)
        elif a.command == 'state':
            from cyber_lion.enterprise.edge_yoke.evidence import verify
            h = Path(a.home)
            result = verify(object_bytes(read_regular(h/'snapshot.json')),read_regular(h/'observer.public.hex',128).decode())
        elif a.command == 'demo':
            from cyber_lion.enterprise.edge_yoke.pilot import demo
            result = demo(a.output,host_id=a.host_id,endpoint=a.model_endpoint)
        elif a.command == 'r24-pilot':
            from cyber_lion.enterprise.edge_yoke.observer import load_config
            from cyber_lion.enterprise.edge_yoke.policy import YokePolicy
            from cyber_lion.enterprise.edge_yoke.gate import YokeGate
            from tools.lion_r24_cooperative_pilot import run
            h = Path(a.home);cfg = load_config(h)
            gate = YokeGate(snapshot=h/'snapshot.json',host_id='MOON',public_key=read_regular(h/'observer.public.hex',128).decode(),policy_sha256=YokePolicy(**cfg['policy']).digest())
            result = run(a.output,docker_exe=a.docker_exe,local_model=a.local_model,gate=gate)
        elif a.command == 'export-audit':
            from cyber_lion.enterprise.edge_yoke.evidence import EvidenceJournal,verify_export
            h = Path(a.home)
            if not (h/'evidence.sqlite').is_file():raise EdgeRejected('journal missing')
            raw = EvidenceJournal(h/'evidence.sqlite').export()
            head = verify_export(raw,read_regular(h/'observer.public.hex',128).decode())
            write_new(a.output,raw)
            result = dict(checkpoint=head,export_sha256=digest(raw),remote_witness='NOT_ESTABLISHED')
        elif a.command == 'verify-export':
            from cyber_lion.enterprise.edge_yoke.evidence import verify_export
            result = verify_export(read_regular(a.input,67108864),read_regular(a.public_key,128).decode(),object_bytes(read_regular(a.expected_head)))
        else:
            from cyber_lion.mission_control.artifact_transfer import materialize_bundle
            result = materialize_bundle(read_regular(a.bundle,800000),a.expected_sha256,object_bytes(read_regular(a.binding,8192)),Path(a.private_parent).resolve())
        print(json.dumps(result,ensure_ascii=True,indent=2))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps(dict(status='REJECTED',error=type(exc).__name__+':'+str(exc)),ensure_ascii=True),file=sys.stderr)
        return 2
if __name__ == '__main__':
    raise SystemExit(main())
