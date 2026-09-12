import threading
import unittest
from unittest.mock import Mock, patch

from cyber_lion.mission_control.server import serve


class LifecycleTests(unittest.TestCase):
    def test_shutdown_waits_for_poll_worker(self):
        stopped = threading.Event()
        mc = Mock()
        mc.stop_event = threading.Event()
        def loop():
            mc.stop_event.wait(2)
            stopped.set()
        mc.loop = loop
        http = Mock()
        events = Mock()
        with patch('cyber_lion.mission_control.server.ThreadingHTTPServer', return_value=http):
            serve(mc, events)
        self.assertTrue(stopped.is_set())
        events.close.assert_called_once()
        http.server_close.assert_called_once()

    def test_start_failure_closes_http(self):
        mc = Mock()
        http = Mock()
        events = Mock()
        events.start.side_effect = RuntimeError('fixture')
        with patch('cyber_lion.mission_control.server.ThreadingHTTPServer', return_value=http):
            with self.assertRaises(RuntimeError):
                serve(mc, events)
        http.server_close.assert_called_once()
        events.close.assert_called_once()

    @unittest.skipUnless(__import__('os').name == 'posix', 'CLI uses Linux event credentials')
    def test_cli_failure_closes_database(self):
        from tools import lion_mission_control as cli
        mc = Mock()
        mc.poll_once.side_effect = RuntimeError('fixture')
        with patch.object(cli, 'build', return_value=(mc, Mock())), patch('sys.argv', ['mc','status']):
            with self.assertRaises(RuntimeError):
                cli.main()
        mc.store.close.assert_called_once()
