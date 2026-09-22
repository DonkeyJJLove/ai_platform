#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path

OUT=Path('/mnt/c/Users/d2j3/AppData/Local/LION/sentinelx-bridge/status.json')
HELPER=Path('/usr/local/bin/lion-sentinelx-turn')

def active():
    try:
        return subprocess.run(['systemctl','is-active','--quiet','sentinelx-cloud-core'],timeout=3).returncode==0
    except Exception:
        return False

agent=active()
helper=HELPER.is_file() and os.access(HELPER,os.X_OK)
digest=hashlib.sha256(HELPER.read_bytes()).hexdigest() if helper else None
payload={
    'schema':'lion.sentinelx-bridge.status/v1',
    'observed_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    'state':'READY' if agent and helper else 'DEGRADED',
    'agent_active':agent,
    'helper_ready':helper,
    'helper_sha256':digest,
    'hub':'https://mcp.sentinelx.app',
    'remote_transport':'SENTINELX_MCP',
    'openai_secure_mcp_tunnel_required':False,
    'authority_effect':'NONE',
}
OUT.parent.mkdir(parents=True,exist_ok=True)
tmp=OUT.with_suffix('.tmp')
tmp.write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,OUT)
