from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class R24WorkerCognitiveReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker=(ROOT/"LION/runtime_compat/r24/docker-autonomy/worker.py").read_text(encoding="utf-8")

    def test_status_advertises_cognitive_readiness_contract(self):
        for literal in (
            '"local_model_inference_capable": True',
            '"local_model_route_current"',
            '"mission_control_route_current"',
            '"container_id_current"',
            '"worker_id_current"',
            '"cognitive_readiness"',
            '"NOT_COGNITIVELY_READY"',
        ):
            self.assertIn(literal,self.worker)

    def test_ready_requires_model_and_mission_control_routes(self):
        self.assertIn('values.get("mission_control_reachability") == "OK"',self.worker)
        self.assertIn('values.get("model_reachability") == "OK"',self.worker)
        self.assertIn('else "NOT_COGNITIVELY_READY"',self.worker)


if __name__=="__main__":
    unittest.main()
