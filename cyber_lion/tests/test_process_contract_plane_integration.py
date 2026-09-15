from __future__ import annotations
import hashlib,json,re,subprocess,os,unittest
from pathlib import Path
from tools.lion_rag32_validate import validate

ROOT=Path(__file__).resolve().parents[2]
CAND='LION/rag/lion_project_rag32_v1_4_process_contract_r1'
R1='LION/rag/lion_project_rag32_v1_4_r1'
MANIFEST=re.compile(r'LION_DATA_BEGIN: PACKAGE_MANIFEST\n```json\n(.*?)\n```',re.S)

class ProcessContractPlaneIntegrationTests(unittest.TestCase):
    def test_canonical_entrypoints_route_process_contract_plane(self):
        doc=(ROOT/'LION/architecture/v1_4/LION_PROCESS_CONTRACT_PLANE.md').read_text(encoding='utf-8')
        self.assertIn('DOCUMENT_ID=LION-PROCESS-CONTRACT-PLANE',doc)
        self.assertIn('PHASE_INTENT',doc);self.assertIn('VERIFY_BEFORE_REPAIR',doc);self.assertIn('PCD-0001',doc)
        for rel in ('AGENTS.md','LION/codex/CODEX_PROJECT_INTEGRATION.md','LION/codex/CODEX_RUNBOOK.md','LION/codex/SCAFFOLDING_PROTOCOL.md','.codex/skills/lion-evolution/SKILL.md'):
            text=(ROOT/rel).read_text(encoding='utf-8')
            self.assertIn('LION_PROCESS_CONTRACT_PLANE.md',text,rel)
        self.assertTrue((ROOT/'cyber_lion/process_language/lpcl_run_1_2.ebnf').is_file())
        self.assertIn('COMPLETION=<PREDICATE>=<EXPECTED>',(ROOT/'cyber_lion/process_language/lpcl_run_1_2.ebnf').read_text(encoding='utf-8'))

    def test_new_rag_candidate_uses_reserve_slots_and_validates(self):
        out=validate(ROOT,CAND)
        self.assertEqual((out['status'],out['file_count'],out['source_count']),('PASS',34,123))
        text=(ROOT/CAND/'05_PACKAGE_MANIFEST.md').read_text(encoding='utf-8');m=json.loads(MANIFEST.search(text).group(1))
        self.assertEqual(m['reserved_slots'],6);self.assertEqual(m['attachment_limit'],40)
        self.assertIn('32_CODEX_PROJECT_INTEGRATION.md',m['attachment_files'])
        self.assertIn('33_LION_PROCESS_CONTRACT_PLANE__v1_4_process_contract_r1.md',m['attachment_files'])
        self.assertIn('PROCESS_CONTRACT_SOURCE=',(ROOT/CAND/'00_START_HERE.md').read_text(encoding='utf-8'))
        self.assertIn('process_contract_schema=lion.phase-execution-contract/v1',(ROOT/CAND/'03_STATE_AND_CONTINUATION.md').read_text(encoding='utf-8'))

    def test_candidate_preserves_historical_source_vector(self):
        candidate=json.loads(MANIFEST.search((ROOT/CAND/'05_PACKAGE_MANIFEST.md').read_text(encoding='utf-8')).group(1))
        env=os.environ.copy();env.update({'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'safe.directory','GIT_CONFIG_VALUE_0':str(ROOT)})
        cp=subprocess.run(['git','show','HEAD:'+R1+'/05_PACKAGE_MANIFEST.md'],cwd=ROOT,env=env,capture_output=True,text=True,check=True)
        old=json.loads(MANIFEST.search(cp.stdout).group(1))
        self.assertEqual(candidate['source_count'],old['source_count'])
        self.assertEqual(candidate['source_vector_digest'],old['source_vector_digest'])
        oldvec={x['source_id']:(x['sha256'],x['bytes'],x['virtual_path']) for x in old['sources']}
        newvec={x['source_id']:(x['sha256'],x['bytes'],x['virtual_path']) for x in candidate['sources']}
        self.assertEqual(newvec,oldvec)

if __name__=='__main__':unittest.main()
