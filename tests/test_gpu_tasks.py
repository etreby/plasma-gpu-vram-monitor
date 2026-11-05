import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_helper import helper
import gpu_tasks as tasks


class NvidiaProcessTests(unittest.TestCase):
    def fixture(self):
        return (Path(__file__).parent / 'fixtures/nvidia-processes.xml').read_text()

    def test_processes_match_physical_gpu_and_do_not_leak_paths(self):
        result = tasks.parse_nvidia_xml(self.fixture())
        self.assertEqual(result['0000:02:00.0']['rows'][0]['memoryBytes'], 512 * 1048576)
        self.assertEqual(result['0000:04:00.0']['rows'][0]['memoryBytes'], 1024 * 1048576)
        self.assertEqual(result['0000:02:00.0']['rows'][0]['name'], 'python3')
        self.assertNotIn('/private/path', json.dumps(result))
        self.assertIsNone(result['0000:02:00.0']['rows'][0]['gpuUsage'])

    def test_unknown_and_wine_process_names_are_safe_basenames(self):
        self.assertEqual(tasks.task(1, 'N/A', 'Other')['name'], 'Unknown process')
        self.assertEqual(tasks.task(1, r'C:\users\someone\Game.exe', 'Graphics')['name'], 'Game.exe')

    def test_pmon_column_changes_and_unavailable_vs_zero(self):
        output = ('# gpu pid type sm mem enc dec fb command\n'
                  '# Idx # C/G % % % % MB name\n'
                  '0 100 C 25 10 0 0 512 python3\n'
                  '0 200 G - - - - 64 renderer\n'
                  '1 300 C 0 0 0 0 0 idle-worker\n')
        rows = tasks.parse_pmon(output, {0: 'a', 1: 'b'})
        self.assertEqual(rows[('a', 100)]['gpuUsage'], 25)
        self.assertIsNone(rows[('a', 200)]['gpuUsage'])
        self.assertEqual(rows[('b', 300)]['gpuUsage'], 0)
        self.assertEqual(rows[('a', 100)]['memoryBytes'], 512000000)

    def test_merge_xml_allocation_and_pmon_utilization(self):
        cards = [{'id': '0000:02:00.0', 'driverIndex': 0}]
        def run(args):
            if '-q' in args:
                return self.fixture()
            return '# gpu pid type sm fb command\n0 100 C 25 999 python3\n'
        result = tasks.nvidia_tasks(cards, run)['0000:02:00.0']
        row = next(p for p in result['rows'] if p['pid'] == 100)
        self.assertEqual(row['memoryBytes'], 512 * 1048576)
        self.assertEqual(row['gpuUsage'], 25)
        self.assertEqual(result['status'], 'limited')  # Renderer has no utilization.

    def test_pmon_uses_groups_of_at_most_four_and_no_silent_device_limit(self):
        cards = [{'id': f'0000:{i + 1:02x}:00.0', 'driverIndex': i} for i in range(9)]
        groups = []
        def run(args):
            if '-q' in args:
                return '<nvidia_smi_log/>'
            groups.append(args[-1].split(','))
            return '# gpu pid type sm fb command\n'
        tasks.nvidia_tasks(cards, run)
        self.assertEqual(sorted(len(group) for group in groups), [1, 4, 4])
        self.assertEqual(len({item for group in groups for item in group}), 9)

    def test_driver_errors_are_not_reported_as_empty_idle_gpu(self):
        cards = [{'id': '0000:02:00.0', 'driverIndex': 0}]
        with patch('builtins.print'):
            result = tasks.nvidia_tasks(cards, lambda args: (_ for _ in ()).throw(FileNotFoundError()))
        self.assertEqual(result[cards[0]['id']]['status'], 'unavailable')


class DrmProcessTests(unittest.TestCase):
    def test_fdinfo_prefers_resident_vram_over_total_and_capacity_not_an_engine(self):
        info = tasks.parse_fdinfo('''drm-driver: amdgpu
drm-client-id: 1
drm-pdev: 0000:03:00.0
drm-total-vram: 1024 MiB
drm-resident-vram: 512 MiB
drm-shared-vram: 200 MiB
drm-engine-render: 100000000 ns
drm-engine-capacity-render: 2
''')
        self.assertEqual(info['memoryBytes'], 512 * 1048576)
        self.assertEqual(info['engines'], {'render': (100000000, 2)})

    def test_i915_system_memory_is_labeled_and_not_presented_as_vram(self):
        info = tasks.parse_fdinfo('drm-driver: i915\ndrm-client-id: 7\ndrm-resident-system0: 256 KiB\ndrm-resident-stolen-local0: 0\n')
        self.assertEqual(info['memoryBytes'], 256 * 1024)
        self.assertEqual(info['memoryKind'], 'System-memory GPU buffers')
        self.assertIsNone(tasks.parse_fdinfo('drm-driver: i915\n'))

    def snapshot(self, counter, owners=None, clients=1):
        return {('gpu', str(i)): {'engines': {'render': (counter, 2)},
                    'memoryBytes': 1024, 'memoryKind': 'VRAM resident',
                    'sampleTimeNs': 1000000000 + counter * 2,
                    'owners': owners or {(10, '100', 'renderer')}} for i in range(clients)}

    def test_engine_deltas_normalize_capacity_and_unique_clients_sum(self):
        first = self.snapshot(0, clients=2)
        second = self.snapshot(100000000, clients=2)
        with patch.object(tasks.time, 'sleep'):
            result = tasks.drm_tasks([{'id': 'gpu'}], snapshot=unittest.mock.Mock(side_effect=[(first, 0), (second, 0)]))
        row = result['gpu']['rows'][0]
        self.assertEqual(row['gpuUsage'], 50)  # 25% on each unique client, same engine.
        self.assertEqual(row['memoryBytes'], 2048)
        self.assertIn('overlap', row['note'])

    def test_mixed_memory_scopes_are_not_labeled_as_only_vram(self):
        first, second = self.snapshot(0, clients=2), self.snapshot(100, clients=2)
        for snapshot in (first, second):
            snapshot[('gpu', '1')]['memoryKind'] = 'System-memory GPU buffers'
        with patch.object(tasks.time, 'sleep'):
            result = tasks.drm_tasks([{'id': 'gpu'}], snapshot=unittest.mock.Mock(side_effect=[(first, 0), (second, 0)]))
        self.assertEqual(result['gpu']['rows'][0]['memoryKind'], 'GPU buffers (mixed memory scopes)')

    def test_counter_reset_and_pid_reuse_do_not_produce_spikes(self):
        for before, after in [(self.snapshot(100), self.snapshot(0)),
                              (self.snapshot(0), self.snapshot(100, owners={(10, '200', 'renderer')}))]:
            with patch.object(tasks.time, 'sleep'):
                result = tasks.drm_tasks([{'id': 'gpu'}], snapshot=unittest.mock.Mock(side_effect=[(before, 0), (after, 0)]))
            self.assertIsNone(result['gpu']['rows'][0]['gpuUsage'])

    def test_shared_client_counters_are_attributed_once_but_both_pids_visible(self):
        owners = {(10, '100', 'renderer'), (20, '100', 'child')}
        first, second = self.snapshot(0, owners), self.snapshot(100, owners)
        with patch.object(tasks.time, 'sleep'):
            result = tasks.drm_tasks([{'id': 'gpu'}], snapshot=unittest.mock.Mock(side_effect=[(first, 0), (second, 0)]))
        rows = result['gpu']['rows']
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row['memoryBytes'] or 0 for row in rows), 1024)
        self.assertEqual(next(row for row in rows if row['pid'] == 10)['sharedWith'], [20])

    def test_duplicate_fds_are_one_client_and_malformed_or_exited_processes_skip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = root / '10'
            (process / 'fd').mkdir(parents=True)
            (process / 'fdinfo').mkdir()
            (process / 'comm').write_text('renderer\n')
            (process / 'stat').write_text('10 (renderer) S ' + ' '.join(['0'] * 18 + ['100']))
            text = 'drm-driver: i915\ndrm-client-id: 1\ndrm-pdev: 0000:03:00.0\n'
            for fd in ('3', '4'):
                (process / 'fd' / fd).symlink_to('/dev/dri/renderD128')
                (process / 'fdinfo' / fd).write_text(text)
            clients, denied = tasks.drm_snapshot({'0000:03:00.0'}, proc_root=root, drm_root=root / 'drm')
            self.assertEqual(len(clients), 1)
            self.assertEqual(len(next(iter(clients.values()))['owners']), 1)


class CollectionPrivacyTests(unittest.TestCase):
    def test_diagnostic_does_not_collect_processes_even_when_ui_supports_them(self):
        with patch.object(helper, 'collect', return_value={'ok': True, 'cards': []}) as collect:
            helper.diagnose(Path('/nonexistent'))
            collect.assert_called_once_with()

    def test_one_backend_failure_preserves_other_vendor_results(self):
        cards = [{'id': 'nvidia', 'driverBackend': 'nvidia-smi'}, {'id': 'intel', 'driverBackend': 'i915'}]
        with patch.object(tasks, 'nvidia_tasks', return_value={'nvidia': {'status': 'ok', 'rows': []}}), \
             patch.object(tasks, 'drm_tasks', side_effect=RuntimeError):
            tasks.collect_processes(cards, None)
        self.assertEqual(cards[0]['processInfo']['status'], 'ok')
        self.assertEqual(cards[1]['processInfo']['status'], 'unavailable')

    def test_modules_are_bundled_consistently(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root / 'bin/gpu_tasks.py').read_bytes(), (root / 'plasmoid/contents/scripts/gpu_tasks.py').read_bytes())
