import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_helper import helper
import test_community_support as community


class BroadCoverageTests(unittest.TestCase):
    def test_legacy_nvidia_query_failure_falls_back_to_xml(self):
        xml = (Path(__file__).parent / 'fixtures/nvidia-legacy.xml').read_text()
        with patch.object(helper, 'run', side_effect=[subprocess.CalledProcessError(1, 'nvidia-smi'), xml]) as run:
            card = helper.nvidia_cards({})[0]
        self.assertEqual(run.call_args.args[0], ['nvidia-smi', '-q', '-x'])
        self.assertEqual(card['name'], 'GTX 1080')
        self.assertEqual((card['core'], card['used'], card['total'], card['load']), (48, 1024, 8192, 12))
        self.assertIsNone(card['vram'])
        self.assertIsNone(card['memoryLoad'])
        self.assertEqual(card['thermalSupport'], 'driver-provided')
        self.assertNotIn('PRIVATE', json.dumps(card))
        self.assertNotIn('NOT_FOR_REPORTS', json.dumps(card))

    def test_bad_xml_does_not_raise_or_return_made_up_stats(self):
        with patch.object(helper, 'run', side_effect=[subprocess.CalledProcessError(1, 'nvidia-smi'), '<bad']):
            self.assertEqual(helper.nvidia_cards({}), [])

    def test_pci_address_validation_prevents_truncation_and_bad_paths(self):
        self.assertEqual(helper.canonical_pci('00000000:AB:01.0'), '0000:ab:01.0')
        for value in ('../../../etc', '12345678:01:00.0', '', '01:00.0'):
            self.assertIsNone(helper.canonical_pci(value))

    def test_nouveau_and_legacy_radeon_driver_temperatures(self):
        for driver, vendor in [('nouveau', '0x10de'), ('radeon', '0x1002')]:
            with self.subTest(driver=driver), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture = {'vendor': vendor, 'device': '0x1234', 'driver': driver,
                           'files': {}, 'hwmon': {'name': driver, 'temp1_input': '47000'}}
                device, hwmon = community.StandardDriverTests().make_device(root, fixture)
                cards = helper.sysfs_cards(devices=helper.discover_gpus(root, root / 'empty-drm'))
                self.assertEqual(cards[0]['core'], 47)
                (hwmon / 'temp1_enable').write_text('0')
                self.assertEqual(helper.sysfs_cards(devices=helper.discover_gpus(root, root / 'empty-drm')), [])

    def test_platform_gpu_discovered_through_drm_and_labeled_hwmon(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / 'platform/fde60000.gpu'
            hwmon = device / 'hwmon/hwmon0'
            hwmon.mkdir(parents=True)
            driver = root / 'drivers/panfrost'
            driver.mkdir(parents=True)
            (device / 'driver').symlink_to(driver)
            for name, value in {'name': 'panfrost', 'temp1_label': 'GPU', 'temp1_input': '51000'}.items():
                (hwmon / name).write_text(value)
            drm = root / 'drm/card0'
            drm.mkdir(parents=True)
            (drm / 'device').symlink_to(device)
            devices = helper.discover_gpus(root / 'empty-pci', root / 'drm')
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0]['id'], 'platform:fde60000.gpu')
            self.assertEqual(helper.sysfs_cards(devices=devices)[0]['core'], 51)
            (hwmon / 'temp1_label').unlink()
            self.assertEqual(helper.sysfs_cards(devices=devices), [])

    def test_pci_and_multiple_drm_nodes_deduplicate_physical_gpu(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pci = root / 'pci'
            pci.mkdir()
            fixture = community.StandardDriverTests().fixtures()['amd']
            device, _ = community.StandardDriverTests().make_device(pci, fixture)
            for name in ('card0', 'card1'):
                card = root / 'drm' / name
                card.mkdir(parents=True)
                (card / 'device').symlink_to(device)
            self.assertEqual(len(helper.discover_gpus(pci, root / 'drm')), 1)

    def test_unknown_card_is_detected_without_claiming_telemetry_support(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = {'vendor': '0xffff', 'device': '0x1234', 'driver': 'somegpu',
                       'files': {}, 'hwmon': {'name': 'somegpu'}}
            community.StandardDriverTests().make_device(root, fixture)
            with patch.object(helper, 'PCI_ROOT', root), patch.object(helper, 'DRM_ROOT', root / 'empty'), \
                 patch.object(helper, 'run', side_effect=FileNotFoundError):
                sample = helper.collect()
            self.assertTrue(sample['ok'])
            self.assertEqual(sample['cards'], [])
            self.assertEqual(sample['devices'][0]['status'], 'no-readable-sensors')
            self.assertIn('No readable', sample['message'])

    def test_capability_flags_preserve_real_zero_and_mark_missing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = community.StandardDriverTests().fixtures()['amd']
            fixture['files']['gpu_busy_percent'] = '0'
            device, hwmon = community.StandardDriverTests().make_device(root, fixture)
            (hwmon / 'temp3_input').unlink()
            with patch.object(helper, 'PCI_ROOT', root), patch.object(helper, 'DRM_ROOT', root / 'empty'), \
                 patch.object(helper, 'run', side_effect=FileNotFoundError):
                card = helper.collect()['cards'][0]
            self.assertEqual(card['load'], 0)
            self.assertTrue(card['capabilities']['load'])
            self.assertFalse(card['capabilities']['vram'])
            self.assertIn('vram', card['missingMetrics'])
