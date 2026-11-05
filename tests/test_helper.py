import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
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

    def test_matches_indices_when_nvidia_rows_are_reordered(self):
        temps = {'gpus': [{'index': 0, 'core': 40, 'junction': 55, 'vram': 60},
                          {'index': 1, 'core': 45, 'junction': 58, 'vram': None}]}
        usage = ('1, NVIDIA GeForce RTX 3090, 00000000:04:00.0, 2048, 24576, 20, N/A\n'
                 '0, NVIDIA GeForce RTX 3090, 00000000:02:00.0, 1024, 24576, 10, 5\n')
        with patch.object(helper.shutil, 'which', return_value='/usr/local/bin/gputemps'), \
             patch.object(helper, 'run', side_effect=[json.dumps(temps), usage]), \
             patch.object(helper.Path, 'read_text', return_value='0x3842'):
            sample = helper.collect()
        self.assertEqual(sample['cards'][0]['used'], 1024)
        self.assertEqual(sample['cards'][1]['load'], 20)
        self.assertIsNone(sample['cards'][1]['vram'])
        self.assertIsNone(sample['cards'][1]['memoryLoad'])
        self.assertNotIn('GPU-', json.dumps(sample))

    def test_timeout_returns_valid_error_json(self):
        with patch.object(helper, 'collect', side_effect=subprocess.TimeoutExpired('gputemps', 8)), \
             patch('builtins.print') as output:
            helper.main()
        self.assertFalse(json.loads(output.call_args.args[0])['ok'])

    def test_non_finite_sensor_values_are_unavailable(self):
        for value in ('nan', 'inf', 'N/A', None):
            self.assertIsNone(helper.number(value))


if __name__ == '__main__':
    unittest.main()
