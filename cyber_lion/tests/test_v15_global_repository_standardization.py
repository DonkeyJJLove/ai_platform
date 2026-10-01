import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
V15 = ROOT / 'LION/architecture/v1_5'
STANDARDS = ROOT / 'LION/standards'
PANEL = ROOT / 'LION/panel'

class GlobalRepositoryStandardizationTests(unittest.TestCase):
    def load(self, path: Path):
        return json.loads(path.read_text(encoding='utf-8'))

    def test_exact_baseline_has_ten_repositories(self):
        baseline = self.load(V15 / 'GLOBAL_REPOSITORY_RECONCILIATION_BASELINE_R1.json')
        self.assertEqual(baseline['schema'], 'lion.global-repository-reconciliation-baseline/v1')
        self.assertEqual(len(baseline['repositories']), 10)
        self.assertEqual(len({r['repository'] for r in baseline['repositories']}), 10)
        for row in baseline['repositories']:
            self.assertRegex(row['head'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['tree'], r'^[0-9a-f]{40}$')

    def test_content_census_classifies_every_observed_file(self):
        census = self.load(V15 / 'REPOSITORY_CONTENT_CENSUS.json')
        self.assertEqual(census['schema'], 'lion.repository-content-census/v1')
        self.assertEqual(census['generated_from']['repository_count'], 10)
        self.assertEqual(census['generated_from']['tracked_file_count'], len(census['files']))
        self.assertGreaterEqual(len(census['files']), 2776)
        self.assertTrue(census['classification_policy']['unknown_is_legal'])
        self.assertFalse(census['classification_policy']['static_unreferenced_is_delete_proof'])
        for row in census['files']:
            self.assertTrue(row['classification'])
            if row['sha256'] != 'SELF_REFERENTIAL':
                self.assertRegex(row['sha256'], r'^[0-9a-f]{64}$')

    def test_naming_status_version_standards_are_typed(self):
        naming = self.load(STANDARDS / 'LION_NAMING_STANDARD.json')
        status = self.load(STANDARDS / 'LION_STATUS_MODEL.json')
        version = self.load(STANDARDS / 'LION_VERSION_MODEL.json')
        layout = self.load(STANDARDS / 'LION_REPOSITORY_LAYOUT_STANDARD.json')
        evidence = self.load(STANDARDS / 'LION_CURRENTNESS_EVIDENCE_MODEL.json')
        generated = self.load(STANDARDS / 'LION_GENERATED_OUTPUT_POLICY.json')
        self.assertEqual(naming['canonical']['readme'], 'README.md')
        self.assertEqual(naming['immutable_history_policy'], 'DO_NOT_RENAME_IMMUTABLE_EVIDENCE')
        self.assertIn('currentness', status['planes'])
        self.assertIn('authority', status['planes'])
        self.assertIn('execution', status['planes'])
        self.assertNotEqual(status['planes']['currentness'], status['planes']['execution'])
        self.assertIn('architecture_epoch', version['axes'])
        self.assertIn('runtime_generation', version['axes'])
        self.assertIn('generated', layout['roles'])
        self.assertIn('LIVE_REPOSITORY_OBSERVATION', evidence['evidence_types'])
        self.assertIn('REPRODUCIBLE_OUTPUT', generated['classes'])

    def test_panel_is_first_class_source_bound_subsystem(self):
        catalog = self.load(PANEL / 'PANEL_COMPONENT_CATALOG.json')
        state = self.load(PANEL / 'PANEL_STATE_MODEL.json')
        ids = {row['id'] for row in catalog['components']}
        self.assertIn('operator-shell', ids)
        self.assertIn('mission-control', ids)
        self.assertIn('canonical-model-chat', ids)
        self.assertIn('saas-consumer', ids)
        self.assertEqual(catalog['authority_effect'], 'NONE')
        self.assertIn('RECONCILED', state['operator_execution_states'])
        self.assertIn('AUTHORIZED', state['authority_states'])

    def test_current_docs_no_longer_call_communication_envelope_unintegrated(self):
        root = (ROOT / 'README.md').read_text(encoding='utf-8')
        lion = (ROOT / 'LION/README.md').read_text(encoding='utf-8')
        v15 = (V15 / 'README.md').read_text(encoding='utf-8')
        roadmap = (V15 / 'AI_NATIVE_ROADMAP_NEXT.md').read_text(encoding='utf-8')
        for text in (root, lion, v15, roadmap):
            self.assertNotIn('CommunicationEnvelope pozostaje osobną zmianą', text)
            self.assertNotIn('not part of the integrated master contract surface', text)
        self.assertIn('CommunicationEnvelope', root)
        self.assertIn('INTEGRATED', roadmap)
        self.assertIn('MissionIntent', roadmap)

    def test_semantic_owner_map_remains_unique_and_covers_new_standards(self):
        owners = self.load(V15 / 'semantic_owners.json')['owners']
        concepts = [row['concept'] for row in owners]
        self.assertEqual(len(concepts), len(set(concepts)))
        for concept in ('repository_content_classification','naming_standard','status_model','version_model','panel','branch_reconciliation','test_taxonomy','workflow_taxonomy'):
            self.assertIn(concept, concepts)

    def test_branch_census_never_turns_unknown_into_delete(self):
        value = self.load(V15 / 'BRANCH_RECONCILIATION_R1.json')
        self.assertEqual(len(value['rows']), 88)
        self.assertEqual(value['counts']['ACTIVE'], 10)
        for row in value['rows']:
            if row['classification'] == 'DELETE_ELIGIBLE':
                self.assertEqual(row['ahead_by'], 0)
                self.assertEqual(row['default_branch_references'], [])
            if row['classification'] == 'UNKNOWN':
                self.assertGreater(row['ahead_by'], 0)

    def test_test_and_workflow_census_preserve_historical_regressions(self):
        tests = self.load(V15 / 'TEST_CENSUS.json')
        workflows = self.load(V15 / 'WORKFLOW_CENSUS.json')
        self.assertGreater(tests['counts'].get('HISTORICAL_REGRESSION', 0), 0)
        self.assertGreaterEqual(len(workflows['workflows']), 40)

    def test_core_ci_has_no_retired_r2e_branch_routing(self):
        core = (ROOT / '.github/workflows/cyber-lion-contracts.yml').read_text(encoding='utf-8')
        fleet = (ROOT / '.github/workflows/fleet-effect-budget-r1.yml').read_text(encoding='utf-8')
        self.assertNotIn('mission/r2e3-', core)
        self.assertNotIn('mission/r2e4-', core)
        self.assertNotIn('mission/fleet-aggregate-effect-budget-r1', fleet)
        self.assertIn('- master', fleet)

if __name__ == '__main__':
    unittest.main()
