import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'bin/gpu-panel-data'
loader = importlib.machinery.SourceFileLoader('helper', str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
helper = importlib.util.module_from_spec(spec)
loader.exec_module(helper)


class TelemetryTests(unittest.TestCase):
    def test_bundled_helper_matches_source(self):
        bundled = path.parents[1] / 'plasmoid/contents/scripts/gpu-panel-data.py'
        self.assertEqual(path.read_bytes(), bundled.read_bytes())

    def test_matches_pci_addresses_when_nvidia_rows_are_reordered(self):
        cached = {'0000:02:00.0': {'junction': 55, 'vram': 60},
                  '0000:04:00.0': {'junction': 58, 'vram': None}}
        usage = ('1, NVIDIA GeForce RTX 3090, 00000000:04:00.0, 2048, 24576, 20, N/A, 45, N/A\n'
                 '0, NVIDIA GeForce RTX 3090, 00000000:02:00.0, 1024, 24576, 10, 5, 40, N/A\n')
        with patch.object(helper, 'temperatures', return_value=cached), \
             patch.object(helper, 'run', return_value=usage) as run, \
             patch.object(helper.Path, 'read_text', return_value='0x3842'):
            sample = helper.collect()
        self.assertEqual(sample['cards'][0]['used'], 1024)
        self.assertEqual(sample['cards'][0]['vram'], 60)
        self.assertEqual(sample['cards'][1]['load'], 20)
        self.assertIsNone(sample['cards'][1]['vram'])
        self.assertIsNone(sample['cards'][1]['memoryLoad'])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][0], 'nvidia-smi')

    def test_no_service_keeps_core_usage_and_driver_memory_temperature(self):
        usage = '0, NVIDIA GPU, 00000000:02:00.0, 1, 100, 10, 0, 42, 62\n'
        with patch.object(helper, 'temperatures', return_value={}), \
             patch.object(helper, 'run', return_value=usage), \
             patch.object(helper.Path, 'read_text', side_effect=OSError):
            card = helper.collect()['cards'][0]
        self.assertEqual(card['core'], 42)
        self.assertEqual(card['vram'], 62)
        self.assertIsNone(card['junction'])

    def test_unavailable_memory_does_not_break_usage(self):
        usage = '0, NVIDIA GPU, 00000000:02:00.0, 1, 100, 10, 0, 42, N/A\n'
        with patch.object(helper, 'temperatures', return_value={}), \
             patch.object(helper, 'run', return_value=usage), \
             patch.object(helper.Path, 'read_text', side_effect=OSError):
            card = helper.collect()['cards'][0]
        self.assertIsNone(card['vram'])
        self.assertEqual(card['used'], 1)

    def test_stale_future_wrong_schema_and_broken_cache_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'sample.json'
            for value in ({'schema': 1, 'timestamp': 80, 'cards': {}},
                          {'schema': 1, 'timestamp': 101, 'cards': {}},
                          {'schema': 2, 'timestamp': 99, 'cards': {}},
                          {'schema': 1, 'timestamp': 99, 'cards': []}, None):
                cache.write_text(json.dumps(value))
                self.assertEqual(helper.temperatures(cache, now=100), {})
            cache.write_text('{bad')
            self.assertEqual(helper.temperatures(cache, now=100), {})
            cache.write_text(json.dumps({'schema': 1, 'timestamp': 99, 'cards': {'a': {}}}))
            self.assertEqual(helper.temperatures(cache, now=100), {'a': {}})

    def test_timeout_returns_valid_error_json(self):
        with patch.object(helper, 'collect', side_effect=subprocess.TimeoutExpired('nvidia-smi', 8)), \
             patch('builtins.print') as output:
            helper.main()
        self.assertFalse(json.loads(output.call_args.args[0])['ok'])

    def test_non_finite_sensor_values_are_unavailable(self):
        for value in ('nan', 'inf', 'N/A', None):
            self.assertIsNone(helper.number(value))
        for value in (-1, 0, 127, 999):
            self.assertIsNone(helper.thermal(value))


if __name__ == '__main__':
    unittest.main()
