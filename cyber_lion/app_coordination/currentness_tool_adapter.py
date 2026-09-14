from datetime import datetime,timezone
from hashlib import sha256
import json
from .lion_context_provider import FED

def _require_provider(provider):
    if not callable(provider):raise ValueError('explicit read-only currentness provider required')
    return provider

def _branch(provider,repo,branch):
    d=_require_provider(provider)('github_branch',{'repository':repo,'branch':branch})
    if type(d) is not dict or not isinstance(d.get('head'),str) or not isinstance(d.get('tree'),str):raise ValueError('currentness provider result')
    return {'repository':repo,'branch':branch,'head':d['head'],'tree':d['tree']}

def read_currentness(subject,provider):
    at=datetime.now(timezone.utc).isoformat();provider=_require_provider(provider)
    try:
        if subject=='AI_PLATFORM_MASTER':
            x=_branch(provider,'DonkeyJJLove/ai_platform','master')
            return {'subject':subject,'observed_identity':x,'observed_at':at,'source':'EXPLICIT_READ_ONLY_PROVIDER','status':'CURRENT','digest':x['head'],'authority_effect':'NONE'}
        if subject=='FEDERATION_DEFAULT_BRANCHES':
            x=tuple(_branch(provider,r,b) for r,b in FED);d=sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            return {'subject':subject,'observed_identity':x,'observed_at':at,'source':'EXPLICIT_READ_ONLY_PROVIDER','status':'CURRENT','digest':d,'authority_effect':'NONE'}
        if subject=='LOCAL_MODEL_RUNTIME':
            x=provider('local_model',{})
            if type(x) is not dict:raise ValueError('model provider result')
            return {'subject':subject,'observed_identity':x,'observed_at':at,'source':'EXPLICIT_READ_ONLY_PROVIDER','status':'CURRENT' if x.get('models') else 'UNKNOWN','digest':sha256(json.dumps(x,sort_keys=True).encode()).hexdigest(),'authority_effect':'NONE'}
    except Exception:pass
    return {'subject':subject,'observed_identity':None,'observed_at':at,'source':'unavailable','status':'UNKNOWN','digest':None,'authority_effect':'NONE'}
