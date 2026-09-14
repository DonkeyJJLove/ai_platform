from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class Epoch3UiStabilityContractTests(unittest.TestCase):
    def test_mission_control_refresh_is_queued_and_viewport_preserved(self):
        text=(ROOT/'deploy/mission-control/v3/control-v3.js').read_text(encoding='utf-8')
        self.assertIn('MC_REFRESH_PENDING', text)
        self.assertIn('mcCaptureViewport', text)
        self.assertIn('mcRestoreViewport', text)
        self.assertIn('requestedMissionId!==MC_SELECTED', text)
        self.assertIn('queueMicrotask(mcRefresh)', text)

    def test_lpcl_panel_refresh_is_queued_stale_safe_and_viewport_preserved(self):
        text=(ROOT/'cyber_lion/app_coordination/local_intelligence_gateway.py').read_text(encoding='utf-8')
        self.assertIn('missionsRefreshPending', text)
        self.assertIn('captureViewport()', text)
        self.assertIn('restoreViewport(vp)', text)
        self.assertIn('requestedMissionId!==selectedMissionId', text)
        self.assertIn('queueMicrotask(refreshMissions)', text)

if __name__ == '__main__':
    unittest.main()
