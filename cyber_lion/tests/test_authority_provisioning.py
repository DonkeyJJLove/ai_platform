from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import inspect,sqlite3,tempfile,unittest
from pathlib import Path
from cyber_lion.contracts.authority_provisioning import AuthorityEpochBootstrap,AuthorityIssuerBinding,AuthorityProvisioningDecision,AuthorityProvisioningRequest,AuthorityRootBootstrap,MergeMethodPolicy,PRAuthorityProvisioningTransaction
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import AuthorityLookupKey,canonical_pr_authority_resource,canonical_source_lineage_digest
from cyber_lion.enterprise.authority_provisioning import AuthorityProvisioningError,SQLiteAuthorityProvisioningStore,authority_provisioning_schema_sql
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

REPO="DonkeyJJLove/ai_platform"; BASE="a"*40; HEAD="b"*40; MISSION="E006-MERGE-AUTHORITY"; POLICY="sha256:"+"c"*64
ADMIN="authority-admin"; ROOT_ISSUER="root-issuer"; DELEGATOR="authority-delegator"; EXECUTOR="merge-executor"; REQUESTER="merge-requester"; DOMAIN="lion.prod"; TENANT="tenant"; ORG="org"; NOW="2026-08-27T15:00:00+00:00"
def sig(key,alg="TEST-ALG"): return f"sig:{key}:{alg}"
def verifier(_payload,signature,key_id,algorithm): return signature==sig(key_id,algorithm)

class AuthorityProvisioningTests(unittest.TestCase):
 def setUp(self):
  self.repo=tempfile.TemporaryDirectory(); self.data=tempfile.TemporaryDirectory(); self.db=Path(self.data.name)/"authority.sqlite"
  sqlite3.connect(self.db).close(); sqlite3.connect(self.db).executescript(authority_provisioning_schema_sql()).close()
  self.store=SQLiteAuthorityProvisioningStore(str(self.db),repository_root=self.repo.name)
 def tearDown(self): self.repo.cleanup(); self.data.cleanup()
 def reset(self): self.tearDown(); self.setUp()
 def binding(self,subject,role,key): return AuthorityIssuerBinding(subject,DOMAIN,key,"TEST-ALG",role,f"control-plane:{subject}").validate()
 def build(self,*,method="merge",requester=REQUESTER,root_subject=DELEGATOR,leaf_issuer=DELEGATOR,revoked=(),bindings=None):
  admin_key="admin-key"; root_key="root-key"; leaf_key="leaf-key"
  request=AuthorityProvisioningRequest("req-1",REPO,232,BASE,HEAD,MISSION,"merge_pull_request",method,POLICY,requester,EXECUTOR,"2026-08-27T14:55:00+00:00").validate()
  epoch=AuthorityEpochBootstrap(DOMAIN,TENANT,ORG,MISSION,7,tuple(revoked),ADMIN,admin_key,"TEST-ALG","2026-08-27T14:00:00+00:00","control-plane:epoch",sig(admin_key)).validate()
  key=AuthorityLookupKey(REPO,232,BASE,HEAD,MISSION,"leaf-grant").validate(); resource=canonical_pr_authority_resource(key)
  root=AuthorityGrant("1.1.0","root-grant",ROOT_ISSUER,root_subject,TENANT,ORG,MISSION,"merge-authority","1",("merge_pull_request",),(resource,),"external_write",(f"merge_method:{method}",),None,"2026-08-27T14:00:00+00:00","2026-08-28T14:00:00+00:00",7,POLICY,"sha256:"+"d"*64,sig(root_key),True,1).validate()
  leaf=AuthorityGrant("1.1.0","leaf-grant",leaf_issuer,EXECUTOR,TENANT,ORG,MISSION,"merge-authority","1",("merge_pull_request",),(resource,),"external_write",(f"merge_method:{method}",),"root-grant","2026-08-27T14:10:00+00:00","2026-08-28T13:00:00+00:00",7,POLICY,"sha256:"+"d"*64,sig(leaf_key),False,0).validate()
  rootb=AuthorityRootBootstrap(epoch.digest(),root.grant_id,root.digest(),ADMIN,admin_key,"TEST-ALG","2026-08-27T14:01:00+00:00","control-plane:root",sig(admin_key)).validate()
  policy=MergeMethodPolicy("merge-policy","1",REPO,method,ADMIN,POLICY,"2026-08-27T14:00:00+00:00","2026-08-28T14:00:00+00:00",admin_key,"TEST-ALG",sig(admin_key)).validate()
  bs=bindings or (self.binding(ADMIN,"provisioning-administrator",admin_key),self.binding(ROOT_ISSUER,"authority-issuer",root_key),self.binding(DELEGATOR,"authority-issuer",leaf_key))
  tx=PRAuthorityProvisioningTransaction("tx-1",request,policy,epoch,rootb,bs,canonical_source_lineage_digest((root,leaf)),leaf.grant_id,"control-plane:tx").validate()
  decision=AuthorityProvisioningDecision("decision-1",tx.digest(),"ALLOW",ADMIN,admin_key,"TEST-ALG","2026-08-27T14:58:00+00:00",sig(admin_key)).validate()
  return tx,decision,(root,leaf)
 def bootstrap(self,tx,lineage): return self.store.bootstrap_authority_context(epoch_bootstrap=tx.epoch_bootstrap,root_bootstrap=tx.root_bootstrap,root_grant=lineage[0],issuer_bindings=tx.issuer_bindings,administrator_verifier=verifier,authority_verifier=verifier,provisioned_at=NOW)
 def provision(self,tx,decision,lineage): return self.store.provision_pr_authority(transaction=tx,decision=decision,lineage=lineage,administrator_verifier=verifier,authority_verifier=verifier,provisioned_at=NOW)
 def rebound(self,tx,**request_changes):
  req=replace(tx.request,**request_changes); tx2=replace(tx,request=req); return tx2,AuthorityProvisioningDecision("decision-2",tx2.digest(),"ALLOW",ADMIN,"admin-key","TEST-ALG","2026-08-27T14:58:00+00:00",sig("admin-key")).validate()
 def counts(self):
  with sqlite3.connect(self.db) as c: return tuple(c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("pr_bootstrap","authority_lineage","authority_provisioning_receipt"))

 def test_positive_atomic_context_and_pr_provisioning(self):
  tx,d,lineage=self.build(); self.bootstrap(tx,lineage); r=self.provision(tx,d,lineage)
  self.assertEqual(r.operation_kind,"PR_AUTHORITY_PROVISIONING"); self.assertEqual(self.counts(),(1,1,2))

 def test_root_and_leaf_self_authority_denied(self):
  tx,d,lineage=self.build(root_subject=ROOT_ISSUER)
  with self.assertRaises(AuthorityProvisioningError): self.bootstrap(tx,lineage)
  tx,d,lineage=self.build(root_subject=EXECUTOR,leaf_issuer=EXECUTOR); self.bootstrap(tx,lineage)
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)

 def test_unknown_and_ambiguous_issuer_denied(self):
  tx,d,lineage=self.build(); reduced=tuple(b for b in tx.issuer_bindings if b.subject_id!=DELEGATOR); tx=replace(tx,issuer_bindings=reduced); d=replace(d,transaction_digest=tx.digest())
  self.bootstrap(tx,lineage[:1])
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)
  self.reset(); tx,d,lineage=self.build(); dup=tx.issuer_bindings+(self.binding(DELEGATOR,"authority-issuer","leaf-key-2"),); tx=replace(tx,issuer_bindings=dup); d=replace(d,transaction_digest=tx.digest())
  self.bootstrap(tx,lineage[:1])
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)

 def test_missing_root_stale_epoch_and_revocation_denied(self):
  tx,d,lineage=self.build()
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)
  self.bootstrap(tx,lineage)
  with sqlite3.connect(self.db) as c: c.execute("UPDATE authority_epoch_state SET epoch=8")
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)
  self.tearDown(); self.setUp(); tx,d,lineage=self.build(revoked=("leaf-grant",)); self.bootstrap(tx,lineage)
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)

 def test_exact_binding_substitutions_denied(self):
  for field,value in (("base_sha","e"*40),("head_sha","f"*40),("pr_number",233),("repository","Other/repo"),("mission_id","OTHER")):
   with self.subTest(field=field):
    self.reset(); tx,d,lineage=self.build(); self.bootstrap(tx,lineage)
    with self.assertRaises(Exception):
     tx2,d2=self.rebound(tx,**{field:value}); self.provision(tx2,d2,lineage)
  self.reset(); tx,d,lineage=self.build(); self.bootstrap(tx,lineage); tx2=replace(tx,request=replace(tx.request,merge_method="squash"))
  with self.assertRaises(Exception): tx2.validate()
  with self.assertRaises(Exception): replace(tx.request,action="workflow_dispatch").validate()

 def test_role_separation_denied(self):
  tx,d,lineage=self.build(requester=DELEGATOR); self.bootstrap(tx,lineage)
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)
  tx,d,lineage=self.build(); bs=(self.binding(ROOT_ISSUER,"provisioning-administrator","admin-key"),self.binding(ROOT_ISSUER,"authority-issuer","root-key"),self.binding(DELEGATOR,"authority-issuer","leaf-key")); epoch=replace(tx.epoch_bootstrap,administrator_subject_id=ROOT_ISSUER); rootb=replace(tx.root_bootstrap,epoch_bootstrap_digest=epoch.digest(),administrator_subject_id=ROOT_ISSUER); tx=replace(tx,epoch_bootstrap=epoch,root_bootstrap=rootb,issuer_bindings=bs)
  with self.assertRaises(AuthorityProvisioningError): self.bootstrap(tx,lineage)

 def test_bad_admin_signature_denied_before_write(self):
  tx,d,lineage=self.build(); epoch=replace(tx.epoch_bootstrap,signature="bad"); rootb=replace(tx.root_bootstrap,epoch_bootstrap_digest=epoch.digest()); tx=replace(tx,epoch_bootstrap=epoch,root_bootstrap=rootb)
  with self.assertRaises(AuthorityProvisioningError): self.bootstrap(tx,lineage)
  self.assertEqual(self.counts(),(0,0,0))

 def test_partial_state_and_replay_denied(self):
  tx,d,lineage=self.build(); self.bootstrap(tx,lineage); req=tx.request
  with sqlite3.connect(self.db) as c: c.execute("INSERT INTO pr_bootstrap VALUES(?,?,?,?,?,?)",(req.repository,req.pr_number,req.base_sha,req.head_sha,req.merge_method,"{}"))
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)
  self.tearDown(); self.setUp(); tx,d,lineage=self.build(); self.bootstrap(tx,lineage); self.provision(tx,d,lineage)
  with self.assertRaises(AuthorityProvisioningError): self.provision(tx,d,lineage)

 def test_atomic_rollback_on_lineage_insert_failure(self):
  tx,d,lineage=self.build(); self.bootstrap(tx,lineage)
  with sqlite3.connect(self.db) as c: c.execute("CREATE TRIGGER fail_lineage BEFORE INSERT ON authority_lineage BEGIN SELECT RAISE(ABORT,'fail'); END;")
  with self.assertRaises(sqlite3.DatabaseError): self.provision(tx,d,lineage)
  self.assertEqual(self.counts(),(0,0,1))

 def test_store_rejects_repository_local_database(self):
  p=Path(self.repo.name)/"db.sqlite"; sqlite3.connect(p).close()
  with self.assertRaises(AuthorityProvisioningError): SQLiteAuthorityProvisioningStore(str(p),repository_root=self.repo.name)

 def test_no_signing_secret_provider_selection_or_effect_surface(self):
  import cyber_lion.enterprise.authority_provisioning as m
  source=inspect.getsource(m)
  for forbidden in ("private_key","PRIVATE KEY","os.environ","importlib","urllib.request","requests.","subprocess.","git push","github."): self.assertNotIn(forbidden,source)
  inv=EffectSurfaceScanner().scan(repository=REPO,revision="a"*40,tree_digest="b"*40,sources={"cyber_lion/enterprise/authority_provisioning.py":source})
  self.assertEqual(len(inv.unclassified_refs),0); self.assertTrue(inv.surfaces); self.assertTrue(all(s.effect_class=="persistent_state.write" for s in inv.surfaces)); self.assertTrue(all(s.target_class=="runtime" for s in inv.surfaces))

if __name__=="__main__": unittest.main()
