import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'cyber_lion/mission_control/static'


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.forms = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'form':
            self.forms.append(attrs)


class UiTests(unittest.TestCase):
    def test_generic_ui_contract_and_read_only_controls(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        script = (STATIC / 'app.js').read_text(encoding='utf-8')
        parser = Structure()
        parser.feed(html)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertFalse(parser.forms)
        for required in ('registry', 'processClass', 'participants', 'artifacts',
                         'receipts', 'phases', 'verification', 'cleanup', 'recentEvents'):
            self.assertIn(required, parser.ids)
        self.assertIn('<title>LION Mission Control</title>', html)
        self.assertIn('<h1>LION MISSION CONTROL</h1>', html)
        for forbidden in ('Vulnerability Knowledge Tool', 'Fuzzing Campaign',
                          'Engage VKT Swarm', 'method:', 'XMLHttpRequest',
                          'MATERIALIZE_VKT_PODS', 'kubectl'):
            self.assertNotIn(forbidden, html + script)
        self.assertIn('Vulnerability Knowledge Test', script)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for UI behavior tests')
    def test_rendering_and_async_selection_regressions(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('mission_control_ui_test.cjs'))],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
