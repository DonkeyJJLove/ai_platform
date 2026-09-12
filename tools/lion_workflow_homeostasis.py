"""Read-only workflow homeostasis audit for LION.

Critical evidence workflows fail closed on identity/evidence defects. Other
workflows are classified and reported without silently changing execution semantics.
"""
from __future__ import annotations
from hashlib import sha256
import argparse,json,re
from pathlib import Path
DOMAIN=b"LION/WORKFLOW-HOMEOSTASIS/1\0"
CRITICAL={"bandit-security.yml","lion-r22c-full-symbol-census.yml","lion-rag32-validate.yml","lion-git-logical-tree.yml","lion-workflow-homeostasis.yml"}
OBSERVATION_WORKFLOWS={"lion-code-perception-observation.yml","lion-group-channel.yml"}
LIVE_PROOF_WORKFLOWS={"f009-live-runtime-proof.yml"}

def _exact_head_tree_binding(text):
    # Accept shell and PowerShell equivalents, but require evidence for both the
    # checked-out commit and its tree. Merely passing expected_master inputs is
    # insufficient without an actual Git readback.
    head = ('git rev-parse HEAD' in text or 'git rev-parse HEAD).Trim()' in text)
    direct_tree = ('HEAD^{tree}' in text or '--format=%T HEAD' in text)
    synthetic_tree = ('PR_EXECUTION_TREE' in text and 'PR_CANDIDATE_TREE' in text and 'git", "cat-file", "-p", "HEAD"' in text)
    return head and (direct_tree or synthetic_tree)

def _workflow_class(name,text,writes):
    if name in CRITICAL:return 'CRITICAL_EVIDENCE'
    if writes:return 'EXTERNAL_WRITE'
    if 'self-hosted' in text:return 'SELF_HOSTED_RUNTIME'
    if name in LIVE_PROOF_WORKFLOWS:return 'LIVE_PROOF'
    if name in OBSERVATION_WORKFLOWS:return 'OBSERVATION'
    return 'READ_ONLY_CI'
class WorkflowAuditError(ValueError):pass
def _run_block_syntax_defects(text):
 lines=text.splitlines(); defects=[]
 for i,line in enumerate(lines):
  m=re.match(r'^(\s*)(?:-\s+)?run:\s*[|>]\s*$',line)
  if not m: continue
  key_indent=len(m.group(1)); j=i+1
  while j<len(lines):
   raw=lines[j]; stripped=raw.strip()
   if not stripped: j+=1; continue
   indent=len(raw)-len(raw.lstrip(' '))
   if indent>key_indent: j+=1; continue
   if stripped.startswith('#'): j+=1; continue
   if re.match(r'^(?:-\s+)?[A-Za-z_][A-Za-z0-9_.-]*\s*:',stripped): break
   defects.append(f'RUN_BLOCK_INDENT_ESCAPE:{j+1}')
   j+=1
 return defects
def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _permissions(text):
 out=[];active=False
 for line in text.splitlines():
  if line.startswith('permissions:'):active=True;continue
  if active:
   if line and not line.startswith(' '):active=False
   elif re.match(r'^\s{2,}[A-Za-z0-9_-]+:\s*[A-Za-z]+\s*$',line):out.append(line.strip())
 return out
def audit(root):
 root=Path(root).resolve();wf=root/'.github/workflows'
 if not wf.is_dir():raise WorkflowAuditError('workflow root')
 rows=[]
 for p in sorted(list(wf.glob('*.yml'))+list(wf.glob('*.yaml'))):
  t=p.read_text(encoding='utf-8');perms=_permissions(t);writes=sorted(x for x in perms if x.endswith(': write'));checkout='actions/checkout@' in t
  workflow_class=_workflow_class(p.name,t,writes)
  row={"name":p.name,"sha256":sha256(p.read_bytes()).hexdigest(),"workflow_class":workflow_class,"semantic_mutation_policy":"AUTO_LOCAL_HARDEN" if workflow_class in {"CRITICAL_EVIDENCE","READ_ONLY_CI","OBSERVATION"} else "FAMILY_REVIEW_REQUIRED","critical_evidence":p.name in CRITICAL,"permissions":perms,"write_permissions":writes,"uses_checkout":checkout,"persist_credentials_false":('persist-credentials: false' in t) if checkout else True,"bounded_timeout":'timeout-minutes:' in t,"concurrency":'concurrency:' in t,"explicit_head_tree_binding":_exact_head_tree_binding(t),"artifact_upload":'actions/upload-artifact@v4' in t,"artifact_sha_binding":('_SHA256' in t and 'sha256sum' in t),"secret_reference":'secrets.' in t,"run_block_syntax_defects":_run_block_syntax_defects(t)}
  defects=["WORKFLOW_SYNTAX_"+x for x in row['run_block_syntax_defects']]
  if row['critical_evidence']:
   if 'contents: read' not in perms:defects.append('CRITICAL_MINIMUM_CONTENTS_READ_MISSING')
   if writes:defects.append('CRITICAL_WRITE_PERMISSION')
   if not row['persist_credentials_false']:defects.append('CRITICAL_CHECKOUT_CREDENTIALS_PERSIST')
   if not row['bounded_timeout']:defects.append('CRITICAL_TIMEOUT_MISSING')
   if not row['concurrency']:defects.append('CRITICAL_CONCURRENCY_MISSING')
   if not row['explicit_head_tree_binding']:defects.append('CRITICAL_HEAD_TREE_BINDING_MISSING')
   if row['secret_reference']:defects.append('CRITICAL_SECRET_REFERENCE')
   if not row['artifact_upload']:defects.append('CRITICAL_ARTIFACT_UPLOAD_MISSING')
   if not row['artifact_sha_binding']:defects.append('CRITICAL_ARTIFACT_HASH_MISSING')
  advisory=[]
  if checkout and not row['persist_credentials_false']:advisory.append('CHECKOUT_CREDENTIALS_NOT_DISABLED')
  if not row['bounded_timeout']:advisory.append('TIMEOUT_MISSING')
  if not row['concurrency']:advisory.append('CONCURRENCY_MISSING')
  if checkout and not row['explicit_head_tree_binding']:advisory.append('EXPLICIT_HEAD_TREE_BINDING_MISSING')
  row['family_review_required']=workflow_class in {'SELF_HOSTED_RUNTIME','EXTERNAL_WRITE'} and bool(advisory)
  row['blocking_defects']=defects;row['advisory_findings']=advisory;rows.append(row)
 classes={name:sum(1 for row in rows if row['workflow_class']==name) for name in sorted({row['workflow_class'] for row in rows})}
 core={"schema":"lion.workflow-homeostasis/v2","workflow_count":len(rows),"workflow_classes":classes,"critical_workflows":sorted(CRITICAL),"workflows":rows,"semantics":"Critical evidence defects block. Read-only CI and observation may be locally hardened without widening effects. Self-hosted runtime and external-write workflows require family-specific semantic review before mutation."}
 core['blocking_defect_count']=sum(len(x['blocking_defects']) for x in rows);core['advisory_finding_count']=sum(len(x['advisory_findings']) for x in rows);core['family_review_workflow_count']=sum(1 for x in rows if x['family_review_required']);core['audit_digest']=sha256(DOMAIN+_canonical(core)).hexdigest();return core
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--repository',default='.');a=ap.parse_args(argv);v=audit(a.repository);print(json.dumps(v,sort_keys=True,indent=2));raise SystemExit(2 if v['blocking_defect_count'] else 0)
if __name__=='__main__':main()
