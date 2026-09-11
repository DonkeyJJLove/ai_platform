from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.lion_native_host_preflight import GIB, assess_capacity, observe


class NativeHostPreflightTests(unittest.TestCase):
    def test_capacity_boundary_and_shortfall(self):
        self.assertEqual(assess_capacity(64 * GIB, 64)['status'], 'SUFFICIENT')
        result = assess_capacity(64 * GIB - 1, 64)
        self.assertEqual(result['status'], 'INSUFFICIENT')
        self.assertEqual(result['shortfall_bytes'], 1)

    def test_invalid_budget_cannot_pass(self):
        for value in (0, -1, True, 1.5, float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess_capacity(GIB, value)

    def test_wsl_observation_does_not_attest_native_host(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('tools.lion_native_host_preflight.platform.system', return_value='Linux'), \
                 patch('tools.lion_native_host_preflight.platform.release', return_value='6.6-microsoft-standard-WSL2'):
                result = observe(Path(directory), 1)
        self.assertTrue(result['wsl_detected'])
        self.assertEqual(result['physical_failure_domain'], 'NOT_ATTESTED')
        self.assertEqual(result['deployment_readiness'], 'NOT_ASSESSED')

    def test_missing_directory_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / 'uncreated'
            with self.assertRaises(FileNotFoundError):
                observe(missing, 1)
            self.assertFalse(missing.exists())

    def test_file_cannot_be_selected_as_storage_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'file'
            file.write_text('retained', encoding='utf-8')
            with self.assertRaises(ValueError):
                observe(file, 1)
            self.assertEqual(file.read_text(encoding='utf-8'), 'retained')


if __name__ == '__main__':
    unittest.main()
