from __future__ import annotations
import urllib.error,urllib.request
from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest
from cyber_lion.enterprise.actions_run_cancel_mediation import CanonicalActionsRunCancelAdmission,DurableActionsRunCancelFence,ActionsRunCancelMediationError,actions_run_cancel_effect_key

class ExactActionsRunCancelEffectProvider:
    API_ORIGIN="https://api.github.com"
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl): return None
    def __init__(self,*,repository:str,token:str,fence:DurableActionsRunCancelFence):
        if repository!="DonkeyJJLove/ai_platform": raise ActionsRunCancelMediationError("repository denied")
        if not isinstance(token,str) or not token: raise ActionsRunCancelMediationError("credential unavailable")
        if type(fence) is not DurableActionsRunCancelFence: raise ActionsRunCancelMediationError("exact fence required")
        self._repository=repository; self._token=token; self._fence=fence
    def cancel_exact(self,request:ActionsRunCancelRequest,admission:CanonicalActionsRunCancelAdmission)->None:
        if type(request) is not ActionsRunCancelRequest or type(admission) is not CanonicalActionsRunCancelAdmission: raise ActionsRunCancelMediationError("exact request/admission required")
        admission.validate(); admission.binds(request)
        if request.repository!=self._repository or admission.repository!=self._repository: raise ActionsRunCancelMediationError("repository substitution")
        key=actions_run_cancel_effect_key(request,admission)
        if self._fence.get(key).state!="ATTEMPTED": raise ActionsRunCancelMediationError("cancel requires ATTEMPTED fence")
        path=f"/repos/{self._repository}/actions/runs/{request.run_id}/cancel"
        req=urllib.request.Request(self.API_ORIGIN+path,data=b"",method="POST",headers={"Authorization":f"Bearer {self._token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"lion-actions-run-cancel/1"})
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(req,timeout=20) as response:
                if response.status!=202: raise ActionsRunCancelMediationError(f"cancel not accepted: {response.status}")
                response.read()
        except urllib.error.HTTPError as exc:
            raise ActionsRunCancelMediationError(f"cancel failed: {exc.code}") from exc
