import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_helper import helper
import test_reader as reader_tests
reader = reader_tests.reader

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def test_each_experimental_profile_requires_specific_opt_in(self):
        for pci_id, profile in reader.PROFILES.items():
            if profile['tier'] != 'experimental':
                continue
            with self.subTest(pci_id=f'{pci_id:04x}'), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                device = reader_tests.ReaderTests().make_device(root, hex(pci_id))
                with patch.object(reader, 'register_value', return_value=60 * 32) as read:
                    sample = reader.sample(root)
                    read.assert_not_called()
                    self.assertFalse(sample['cards'])
                    self.assertEqual(sample['support'][device.name]['tier'], 'experimental')
                    self.assertFalse(sample['support'][device.name]['enabled'])
                    sample = reader.sample(root, experimental_devices=(pci_id,))
                    self.assertEqual(read.call_count, 2)
                    self.assertEqual(sample['cards'][device.name]['support'], 'experimental')

    def test_opt_in_never_allows_unknown_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reader_tests.ReaderTests().make_device(root, '0xffff')
            with patch.object(reader, 'register_value') as read:
                sample = reader.sample(root, experimental_devices=(0xffff,))
                read.assert_not_called()
                self.assertFalse(sample['cards'])

    def test_cli_lists_without_hardware_and_rejects_unknown_opt_in(self):
        script = str(ROOT / 'sensors/gpu-vram-sensors.py')
        result = subprocess.run([sys.executable, script, '--list-support'], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['2204']['tier'], 'verified')
        result = subprocess.run([sys.executable, script, '--once', '--experimental-device', 'ffff'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        result = subprocess.run([sys.executable, script, '--validate-options', '--verified-only', '--experimental-device', '2206'], capture_output=True)
        self.assertEqual(result.returncode, 2)


class StandardDriverTests(unittest.TestCase):
    def make_device(self, root, fixture):
        device = root / '0000:03:00.0'
        device.mkdir()
        for name, value in {'vendor': fixture['vendor'], 'device': fixture['device'], 'class': '0x030000', **fixture['files']}.items():
            (device / name).write_text(value)
        (device / 'driver').symlink_to('/sys/bus/pci/drivers/' + fixture['driver'])
        (device / 'power').mkdir()
        (device / 'power/runtime_status').write_text('active')
        hwmon = device / 'hwmon/hwmon3'
        hwmon.mkdir(parents=True)
        for name, value in fixture['hwmon'].items():
            (hwmon / name).write_text(value)
        return device, hwmon

    def fixtures(self):
        return json.loads((ROOT / 'tests/fixtures/driver-sensors.json').read_text())

    def test_amd_units_labels_usage_and_faults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device, hwmon = self.make_device(root, self.fixtures()['amd'])
            card = helper.sysfs_cards(root)[0]
            self.assertEqual((card['core'], card['junction'], card['vram']), (45, 61, 58))
            self.assertEqual((card['used'], card['total']), (2048, 16384))
            self.assertEqual(card['load'], 37)
            self.assertEqual(card['thermalSupport'], 'driver-provided')
            (hwmon / 'temp3_fault').write_text('1')
            self.assertIsNone(helper.sysfs_cards(root)[0]['vram'])
            (device / 'power/runtime_status').write_text('suspended')
            self.assertEqual(helper.sysfs_cards(root), [])

    def test_intel_only_reports_exposed_sensor_not_shared_ram_as_vram(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device, hwmon = self.make_device(root, self.fixtures()['intel'])
            card = helper.sysfs_cards(root)[0]
            self.assertEqual(card['core'], 42)
            self.assertIsNone(card['vram'])
            self.assertIsNone(card['total'])
            self.assertIsNone(card['load'])
            (hwmon / 'temp1_label').write_text('Package')
            self.assertEqual(helper.sysfs_cards(root), [])

    def test_missing_nvidia_does_not_hide_amd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_device(root, self.fixtures()['amd'])
            with patch.object(helper, 'PCI_ROOT', root), patch.object(helper, 'run', side_effect=FileNotFoundError):
                sample = helper.collect()
            self.assertTrue(sample['ok'])
            self.assertEqual(sample['cards'][0]['vendor'], 'AMD')

    def test_experimental_metadata_reaches_widget(self):
        cache = {'0000:02:00.0': {'vram': 60, 'junction': 54, 'support': 'experimental'}}
        output = '0, NVIDIA GeForce RTX 3080, 00000000:02:00.0, 1, 100, 10, 0, 42, N/A\n'
        with patch.object(helper, 'run', return_value=output):
            card = helper.nvidia_cards(cache)[0]
        self.assertEqual(card['thermalSupport'], 'experimental')
        self.assertEqual(card['temperatureSources']['vram'], 'experimental-register-cache')

    def test_diagnostic_is_whitelisted_and_never_invokes_register_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device, _ = self.make_device(root, self.fixtures()['amd'])
            (device / 'serial').write_text('SECRET_SERIAL')
            with patch.object(helper, 'collect', return_value={'ok': True, 'cards': []}), patch.object(helper, 'run') as run:
                report = helper.diagnose(root)
                run.assert_not_called()
            output = json.dumps(report)
            self.assertNotIn('SECRET_SERIAL', output)
            self.assertNotIn('hostname', output)
            self.assertEqual(report['inventory'][0]['device_id'], '0x744c')
