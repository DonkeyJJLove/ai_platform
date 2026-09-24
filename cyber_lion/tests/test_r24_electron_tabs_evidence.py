from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cyber_lion.mission_control import mission_reconciliation as reconciliation


MISSION = "LION-R24-FULL-CONTROL-PLANE-FEDERATION-64L32M-R1"
NOW = datetime(2026, 9, 24, 13, 15, 0, tzinfo=timezone.utc)
MAIN = """'use strict';
app.enableSandbox();
let activeRightTab='panel';
if(v===mission)return u.origin===new URL(MC).origin;
u.protocol==='lion-tab:';
wc.setWindowOpenHandler(()=>({action:'deny'}));
wc.session.on('will-download',event=>event.preventDefault());
mission.setBounds({x:0,y:0,width:split,height});
panel.setBounds(activeRightTab==='panel'?shown:hidden);saas.setBounds(activeRightTab==='saas'?shown:hidden);
selectRightTab=name=>{activeRightTab=name==='saas'?'saas':'panel';layout();win.setTitle('x')};
const tabHtml='<a href="lion-tab://panel">LPCL PANEL</a><a href="lion-tab://saas">ChatGPT SaaS</a>';
selectRightTab('panel');
const remember=()=>{try{store.rememberConversation(saas.webContents.getURL())}catch{}};
"""
STORE = """class Store {
rememberConversation(url){ return url; }
restoreConversation(){ return this.projectUrl; }
}
"""
OTHER = "'use strict';\nmodule.exports={};\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class R24ElectronTabsEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.live = root / "live"
        self.release = root / "release"
        for base in (self.live, self.release):
            (base / "src").mkdir(parents=True)
            (base / "src/main.cjs").write_text(MAIN, encoding="utf-8")
            (base / "src/store.cjs").write_text(STORE, encoding="utf-8")
            (base / "src/thread-consumer.cjs").write_text(OTHER, encoding="utf-8")
            (base / "src/contract.cjs").write_text(OTHER, encoding="utf-8")
        self.receipt = root / "receipt.json"

    def value(self, *, observed_at="2026-09-24T13:14:30Z"):
        hashes = {rel: sha(self.live / rel) for rel in reconciliation.R24_BROWSER_SOURCE_PATHS}
        value = {
            "schema": "lion.r24-electron-tabs-evidence/v1",
            "mission_id": MISSION,
            "phase_id": "ELECTRON_TABS",
            "observed_at": observed_at,
            "candidate_head": "1" * 40,
            "candidate_tree": "2" * 40,
            "source_sha256": hashes,
            "restart": {"old_pid": 100, "new_pid": 200, "new_alive": True},
            "session": {"before_sha256": "a" * 64, "after_sha256": "a" * 64, "conversation_present_after": True},
            "electron": {
                "main_pid": 200,
                "main_count": 1,
                "renderer_count": 4,
                "executable": r"C:\Users\d2j3\AppData\Local\LION\browser_broker\node_modules\electron\dist\electron.exe",
                "profile": r"C:\Users\d2j3\AppData\Local\LION\r19-browser-broker",
            },
            "panel": {"pid": 300, "health_status": "ok", "authority_effect": "NONE"},
            "authority_effect": "NONE",
        }
        value["receipt_digest"] = hashlib.sha256(reconciliation._canonical(value)).hexdigest()
        self.receipt.write_text(json.dumps(value), encoding="utf-8")
        return value

    def verify(self):
        return reconciliation._r24_electron_tabs_evidence(
            MISSION,
            receipt_path=self.receipt,
            live_root=self.live,
            release_root=self.release,
            require_trusted_owner=False,
            now_value=NOW,
        )

    def test_exact_source_runtime_restart_and_session_evidence_passes(self):
        value = self.value()
        out = self.verify()
        self.assertIsNotNone(out)
        self.assertEqual(out["receipt_digest"], value["receipt_digest"])
        self.assertTrue(out["source_converged"])
        self.assertTrue(out["tab_layout_acceptance"])
        self.assertTrue(out["session_preservation"])
        self.assertTrue(out["restart_durability"])

    def test_source_drift_fails_closed(self):
        self.value()
        (self.live / "src/main.cjs").write_text(MAIN + "\n// drift\n", encoding="utf-8")
        self.assertIsNone(self.verify())

    def test_session_change_fails_closed(self):
        value = self.value()
        value["session"]["after_sha256"] = "b" * 64
        value["receipt_digest"] = hashlib.sha256(reconciliation._canonical({k:v for k,v in value.items() if k!="receipt_digest"})).hexdigest()
        self.receipt.write_text(json.dumps(value), encoding="utf-8")
        self.assertIsNone(self.verify())

    def test_stale_receipt_fails_closed(self):
        self.value(observed_at="2026-09-24T12:00:00Z")
        self.assertIsNone(self.verify())


if __name__ == "__main__":
    unittest.main()
