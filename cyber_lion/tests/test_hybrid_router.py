from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import unittest
from cyber_lion.hybrid_router import *
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

H="a"*64
class HybridRouterTests(unittest.TestCase):
 def req(self,classes=("deterministic","local_model","saas_model"),authority="none"):
  return MissionRouteRequest("mission:d1","proposal.generate",authority,H,"d1-policy",classes).validate()
 def provider(self,pid,cls,*,caps=("proposal.generate",),auth=("none","read"),current=True,available=True):
  return ProviderDescriptor(pid,cls,H,H,caps,auth,current,available,H).validate()
 def policy(self,order=("deterministic","local_model","saas_model")):
  return RoutePolicy("d1-policy",order).validate()
 def test_provider_class_changes_route_not_capability_or_authority(self):
  r=self.req();ps=[self.provider("det","deterministic"),self.provider("local","local_model"),self.provider("saas","saas_model")]
  decisions=[HybridRouter.route(r,self.policy(order),ps) for order in (("deterministic","local_model","saas_model"),("local_model","saas_model","deterministic"),("saas_model","deterministic","local_model"))]
  self.assertEqual({d.provider_class for d in decisions},{"deterministic","local_model","saas_model"})
  self.assertEqual({(d.capability,d.requested_authority,d.action_ir_digest) for d in decisions},{(r.capability,r.requested_authority,r.action_ir_digest)})
  self.assertEqual({(d.authority_effect,d.execution_effect) for d in decisions},{("NONE","NONE")})
 def test_capability_substitution_is_not_a_route(self):
  with self.assertRaises(HybridRouteError):HybridRouter.route(self.req(),self.policy(),[self.provider("x","local_model",caps=("other",))])
 def test_authority_widening_provider_is_not_admissible(self):
  with self.assertRaises(HybridRouteError):HybridRouter.route(self.req(authority="read"),self.policy(),[self.provider("x","local_model",auth=("none",))])
 def test_forged_decision_cannot_change_authority_or_capability(self):
  r=self.req();p=self.provider("local","local_model");pol=self.policy(("local_model","deterministic","saas_model"));d=HybridRouter.route(r,pol,[p])
  for forged in (replace(d,requested_authority="privileged",route_digest=d.route_digest),replace(d,capability="other",route_digest=d.route_digest)):
   with self.assertRaises(HybridRouteError):forged.validate(r,pol,p)
 def test_provider_identity_and_policy_substitution_fail_closed(self):
  r=self.req();p=self.provider("local","local_model");pol=self.policy(("local_model","deterministic","saas_model"));d=HybridRouter.route(r,pol,[p])
  with self.assertRaises(HybridRouteError):d.validate(r,pol,self.provider("other","local_model"))
  with self.assertRaises(HybridRouteError):d.validate(r,self.policy(("saas_model","local_model","deterministic")),p)
 def test_stale_unavailable_duplicate_and_forbidden_providers_fail_closed(self):
  r=self.req(classes=("local_model",));pol=self.policy(("local_model","deterministic","saas_model"))
  for ps in ([self.provider("x","local_model",current=False)],[self.provider("x","local_model",available=False)],[replace(r,forbidden_provider_ids=("x",)),]):
   if ps and isinstance(ps[0],MissionRouteRequest):
    with self.assertRaises(HybridRouteError):HybridRouter.route(ps[0],pol,[self.provider("x","local_model")])
   else:
    with self.assertRaises(HybridRouteError):HybridRouter.route(r,pol,ps)
  with self.assertRaises(HybridRouteError):HybridRouter.route(r,pol,[self.provider("x","local_model"),self.provider("x","local_model")])
 def test_deterministic_tie_break_is_provider_id(self):
  r=self.req(classes=("local_model",));pol=self.policy(("local_model","deterministic","saas_model"))
  d=HybridRouter.route(r,pol,[self.provider("z","local_model"),self.provider("a","local_model")]);self.assertEqual(d.provider_id,"a")
 def test_router_adds_no_effect_surface(self):
  path="cyber_lion/hybrid_router.py";inv=EffectSurfaceScanner().scan(repository="DonkeyJJLove/ai_platform",revision="1"*40,tree_digest="2"*40,sources={path:Path(path).read_text()})
  self.assertEqual(inv.surfaces,());self.assertEqual(inv.unclassified_refs,())

if __name__=="__main__":unittest.main()
