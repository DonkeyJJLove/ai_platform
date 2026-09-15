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


    def test_waiting_controls_are_backend_projected_and_liveness_is_real_heartbeat_driven(self):
        js=(ROOT/'deploy/mission-control/v3/control-v3.js').read_text(encoding='utf-8')
        css=(ROOT/'deploy/mission-control/v3/app.css').read_text(encoding='utf-8')
        html=(ROOT/'deploy/mission-control/v3/index.html').read_text(encoding='utf-8')
        self.assertIn('s.driver_controls||{}',js)
        self.assertIn("['REACQUIRE_CAPABILITIES','Recheck capability'",js)
        self.assertIn("['PAUSE_AUTO_RESUME','Pause auto-resume'",js)
        self.assertNotIn("if(['ACTIVE','WAITING','BLOCKED'].includes(ds))a+=mcbtn('PAUSE','Pause driver')",js)
        self.assertIn('mcRenderLiveness',js);self.assertIn('mcMarkDisconnected',js)
        self.assertIn('MC_LAST_HEARTBEAT_SIGNATURE',js);self.assertIn('heartbeat-pulse',js)
        self.assertIn('animation:mcHeartbeatFlash .45s ease-out 1',css)
        self.assertNotIn('infinite',css.lower())
        self.assertIn('mcLivenessCards',html);self.assertIn('mcWaitingDetail',html);self.assertIn('mcProgressTrack',html);self.assertIn('mcLivenessLine',html)
        self.assertIn('else{mcRenderHeader(s);mcRenderLiveness(s)}',js)


    def test_lpcl_panel_refresh_is_queued_stale_safe_and_viewport_preserved(self):
        text=(ROOT/'cyber_lion/app_coordination/local_intelligence_gateway.py').read_text(encoding='utf-8')
        self.assertIn('missionsRefreshPending', text)
        self.assertIn('captureViewport()', text)
        self.assertIn('restoreViewport(vp)', text)
        self.assertIn('requestedMissionId!==selectedMissionId', text)
        self.assertIn('queueMicrotask(refreshMissions)', text)

if __name__ == '__main__':
    unittest.main()
