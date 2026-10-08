from __future__ import annotations

import ast
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DOM(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.details = {}

    def handle_starttag(self, tag, attrs):
        row = dict(attrs)
        if row.get("id"):
            self.ids.append(row["id"])
        if tag == "a":
            self.links.append(row.get("href"))
        if tag == "details" and row.get("id"):
            self.details[row["id"]] = row


class R4CompactOperatorUI(unittest.TestCase):
    def source(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def panel_ui(self):
        tree = ast.parse(self.source("cyber_lion/app_coordination/local_intelligence_gateway.py"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "UI" for t in node.targets
            ):
                return ast.literal_eval(node.value)
        self.fail("Canonical UI not found")

    def test_main_control_page_is_collapsed_and_links_only_to_native_peers(self):
        page = self.source("deploy/mission-control/v3/index.html")
        tree = DOM()
        tree.feed(page)
        self.assertEqual(len(tree.ids), len(set(tree.ids)))
        self.assertIn("mcFullInspection", tree.details)
        self.assertNotIn("open", tree.details["mcFullInspection"])
        self.assertEqual(
            {x for x in tree.links if x and x.startswith("lion-")},
            {"lion-left://cluster", "lion-left://system", "lion-right://panel"},
        )
        for retained in ("mcV3Registry", "mcV3Logical", "clusterMap", "runs", "recentEvents"):
            self.assertIn(retained, tree.ids)

    def test_canonical_panel_uses_compact_on_demand_mission_drawer(self):
        source = self.panel_ui()
        dom = DOM()
        dom.feed(source)
        self.assertEqual(len(dom.ids), len(set(dom.ids)))
        for id_ in ("missionSidebar", "missionNavToggle", "missionSidebarContents",
                    "missionViewLabel", "missionHistoryToggle", "missionList"):
            self.assertIn(id_, dom.ids)
        self.assertIn(".layout{grid-template-columns:56px minmax(0,1fr)", source)
        self.assertIn(".composer{left:56px}", source)
        self.assertIn("function toggleMissionNav(force)", source)
        self.assertIn("toggleMissionNav(false);refreshMissionProcess()", source)
        self.assertIn("aria-expanded=\"false\"", source)
        self.assertIn("History / Legacy", source)
        self.assertIn("Widok: operacyjne", source)
        self.assertIn("Widok: ", source)
        self.assertIn("execution_controls_allowed===false", source)

    @unittest.skipUnless(shutil.which("node"), "Node.js required for inline JS parse")
    def test_canonical_panel_inline_javascript_is_syntactically_valid(self):
        source = self.panel_ui()
        scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", source, re.S)
        self.assertTrue(scripts, "UI inline JS must be present")
        for js in scripts:
            with tempfile.TemporaryDirectory() as directory:
                f = Path(directory) / "ui.js"
                f.write_text(js, encoding="utf-8")
                out = subprocess.run([shutil.which("node"), "--check", str(f)],
                                     capture_output=True, text=True, timeout=12)
                self.assertEqual(out.returncode, 0, out.stderr)

    def test_exact_static_asset_security_pins_match_new_bytes(self):
        broker = self.source("tools/lion_effect_admission_broker.py")
        for n in ("app.css", "index.html"):
            actual = sha256((ROOT / "deploy/mission-control/v3" / n).read_bytes()).hexdigest()
            self.assertIn('"static/'+n+'":"'+actual+'"', broker)


if __name__ == "__main__":
    unittest.main()
