import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'sensors/gpu-vram-sensors.py'
spec = importlib.util.spec_from_file_location('reader', path)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ReaderTests(unittest.TestCase):
    def test_decoding_and_invalid_registers(self):
        self.assertEqual(reader.decode('vram', 60 * 32), 60)
        self.assertEqual(reader.decode('junction', 57 << 8), 57)
        for channel in ('vram', 'junction'):
            for raw in (0, 0xFFFFFFFF, 0xBADF1234):
                self.assertIsNone(reader.decode(channel, raw))
        self.assertIsNone(reader.decode('junction', 200 << 8))

    def make_device(self, root, device_id='0x2204'):
        device = root / '0000:02:00.0'
        device.mkdir()
        for name, value in {'vendor': '0x10de', 'device': device_id, 'class': '0x030000',
                            'resource': '0x82000000 0x82ffffff 0x40200\n'}.items():
            (device / name).write_text(value)
        (device / 'power').mkdir()
        (device / 'power/runtime_status').write_text('active')
        (device / 'driver').symlink_to('/sys/bus/pci/drivers/nvidia')
        return device

    def test_unsupported_or_suspended_device_never_reads_registers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = self.make_device(root, '0x9999')
            with patch.object(reader, 'register_value') as read:
                self.assertEqual(reader.sample(root)['cards'], {})
                read.assert_not_called()
            (device / 'device').write_text('0x2204')
            (device / 'power/runtime_status').write_text('suspended')
            with patch.object(reader, 'register_value') as read:
                self.assertEqual(reader.sample(root)['cards'], {})
                read.assert_not_called()

    def test_missing_permission_becomes_per_device_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_device(root)
            with patch.object(reader, 'register_value', side_effect=PermissionError):
                sample = reader.sample(root)
            self.assertFalse(sample['cards'])
            self.assertIn('0000:02:00.0', sample['errors'])

    def test_register_mapping_is_read_only_and_page_aligned(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            with (device / 'resource0').open('wb') as out:
                out.truncate(0x21000)
                out.seek(0xE2A8)
                out.write((60 * 32).to_bytes(4, 'little'))
            self.assertEqual(reader.register_value(device, 0xE2A8), 60 * 32)
            self.assertEqual((device / 'resource0').stat().st_size, 0x21000)

    def test_atomic_cache_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'temperatures.json'
            reader.publish({'schema': 1}, destination)
            self.assertEqual(json.loads(destination.read_text()), {'schema': 1})
            self.assertFalse(destination.with_suffix('.new').exists())
