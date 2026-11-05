"""Unprivileged GPU task sampling. SPDX-License-Identifier: GPL-3.0-only."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET


def numeric(value):
    try:
        result = float(value)
        return result if 0 <= result < float('inf') else None
    except (ValueError, TypeError):
        return None


def memory_bytes(value):
    match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(B|bytes|KiB|MiB|GiB|kB|MB|GB)?\s*', value or '')
    if not match:
        return None
    units = {None: 1, 'B': 1, 'bytes': 1, 'KiB': 1024, 'MiB': 1048576,
             'GiB': 1073741824, 'kB': 1000, 'MB': 1000000, 'GB': 1000000000}
    value = numeric(match[1])
    return int(value * units[match[2]]) if value is not None and value * units[match[2]] < float('inf') else None


def pci(value):
    match = re.fullmatch(r'([0-9a-fA-F]{4,8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])', value or '')
    if not match or int(match[1], 16) > 0xffff:
        return None
    return f'{int(match[1], 16):04x}:{match[2].lower()}:{match[3].lower()}.{match[4]}'


def task(pid, name, kind, memory=None, usage=None, memory_kind='VRAM'):
    name = 'Unknown process' if name in (None, '', 'N/A', '-') else Path(name.replace('\\', '/')).name
    return {'pid': int(pid), 'name': name[:160],
            'kind': kind, 'memoryBytes': memory, 'gpuUsage': usage,
            'memoryKind': memory_kind, 'sharedWith': [], 'note': ''}


def parse_nvidia_xml(output):
    result = {}
    tree = ET.fromstring(output)
    for gpu in tree.findall('gpu'):
        identity = pci(gpu.findtext('pci/pci_bus_id'))
        processes = gpu.find('processes')
        if not identity or processes is None or (processes.text or '').strip() in ('N/A', 'Not Supported'):
            continue
        rows = {}
        for process in processes.findall('process_info'):
            pid = process.findtext('pid', '')
            if not pid.isdecimal() or int(pid) <= 0:
                continue
            kind = {'C': 'Compute', 'G': 'Graphics', 'C+G': 'Compute + graphics'}.get(process.findtext('type'), 'Other')
            item = task(pid, process.findtext('process_name'), kind,
                        memory_bytes(process.findtext('used_memory')))
            old = rows.get(item['pid'])
            if old:
                # Avoid adding potentially overlapping graphics/MIG context allocations.
                known = [value for value in (old['memoryBytes'], item['memoryBytes']) if value is not None]
                item['memoryBytes'] = max(known) if known else None
                item['note'] = 'Multiple contexts; allocation may overlap'
            rows[item['pid']] = item
        result[identity] = {'status': 'ok', 'rows': list(rows.values()),
                            'source': 'NVIDIA driver', 'usageLabel': 'SM active time',
                            'note': 'Driver-reported processes. Reserved memory and shared allocations may not sum to device usage.'}
    return result


def parse_pmon(output, index_to_gpu):
    columns = None
    result = {}
    for line in output.splitlines():
        words = line.split()
        if words[:3] == ['#', 'gpu', 'pid']:
            columns = words[1:]
            continue
        if not words or words[0].startswith('#') or not columns:
            continue
        values = line.split(None, len(columns) - 1)
        row = dict(zip(columns, values))
        if not row.get('gpu', '').isdecimal() or not row.get('pid', '').isdecimal():
            continue
        identity = index_to_gpu.get(int(row['gpu']))
        if identity is None:
            continue
        usage = numeric(row.get('sm'))
        usage = usage if usage is not None and usage <= 100 else None
        # pmon documents FB in MB; XML's explicitly tagged MiB takes priority.
        allocation = memory_bytes(row.get('fb', '') + ' MB')
        kind = {'C': 'Compute', 'G': 'Graphics', 'C+G': 'Compute + graphics'}.get(row.get('type'), 'Other')
        result[(identity, int(row['pid']))] = task(row['pid'], row.get('command'), kind, allocation, usage)
    return result


def nvidia_tasks(cards, run):
    if not cards:
        return {}
    try:
        results = parse_nvidia_xml(run(['nvidia-smi', '-q', '-x']))
    except (OSError, subprocess.SubprocessError, ET.ParseError):
        results = {}
    index_to_gpu = {card['driverIndex']: card['id'] for card in cards}
    def sample_group(group):
        try:
            return parse_pmon(run(['nvidia-smi', 'pmon', '-s', 'um', '-c', '1', '-i', ','.join(card['id'] for card in group)]), index_to_gpu)
        except (OSError, subprocess.SubprocessError):
            return {}
    # Older pmon versions support at most four selected devices per invocation.
    groups = [cards[index:index + 4] for index in range(0, len(cards), 4)]
    with ThreadPoolExecutor(max_workers=min(4, len(groups))) as pool:
        samples = list(pool.map(sample_group, groups))
    for sample in samples:
        for (identity, pid), update in sample.items():
            result = results.setdefault(identity, {'status': 'limited', 'rows': [], 'source': 'NVIDIA pmon',
                                      'usageLabel': 'SM active time', 'note': 'Process-list fallback; visibility depends on driver support.'})
            old = next((row for row in result['rows'] if row['pid'] == pid), None)
            if old:
                old['gpuUsage'] = update['gpuUsage']
                if old['memoryBytes'] is None:
                    old['memoryBytes'] = update['memoryBytes']
            else:
                result['rows'].append(update)
    for card in cards:
        result = results.setdefault(card['id'], {'status': 'unavailable', 'rows': [], 'source': 'NVIDIA driver',
                                  'usageLabel': 'SM active time', 'note': 'The driver did not expose a process list.'})
        if any(row['gpuUsage'] is None for row in result['rows']):
            result['status'] = 'limited'
            result['note'] += ' Per-process GPU utilization is unavailable for some tasks; a dash is not 0%.'
    return results


def parse_fdinfo(text):
    fields = {}
    for line in text.splitlines():
        key, separator, value = line.partition(':')
        if separator and key.startswith('drm-'):
            fields[key] = value.strip()
    if not fields.get('drm-driver') or not fields.get('drm-client-id', '').isdecimal():
        return None
    engines = {}
    for key, value in fields.items():
        if not key.startswith('drm-engine-') or key.startswith('drm-engine-capacity-'):
            continue
        match = re.fullmatch(r'(\d+)\s+ns', value)
        if match:
            engine = key.removeprefix('drm-engine-')
            capacity = numeric(fields.get('drm-engine-capacity-' + engine, '1'))
            if capacity and capacity.is_integer():
                engines[engine] = (int(match[1]), int(capacity))
    allocation = None
    memory_kind = 'GPU buffers'
    for prefix in ('drm-resident-', 'drm-memory-', 'drm-total-'):
        local = [(key, memory_bytes(value)) for key, value in fields.items()
                 if key.startswith(prefix) and (key[len(prefix):] == 'vram' or key[len(prefix):].startswith('local'))]
        valid = [value for _, value in local if value is not None]
        if valid:
            allocation = sum(valid)
            memory_kind = 'VRAM resident' if prefix != 'drm-total-' else 'VRAM buffers'
            break
    if allocation is None:
        for prefix in ('drm-resident-', 'drm-memory-', 'drm-total-'):
            regions = [memory_bytes(value) for key, value in fields.items()
                       if key.startswith(prefix) and (key[len(prefix):] in ('memory', 'gtt') or key[len(prefix):].startswith('system'))]
            valid = [value for value in regions if value is not None]
            if valid:
                allocation = sum(valid)
                memory_kind = 'System-memory GPU buffers'
                break
    return {'client': fields['drm-client-id'], 'device': pci(fields.get('drm-pdev')),
            'engines': engines, 'memoryBytes': allocation, 'memoryKind': memory_kind}


def drm_snapshot(identities, proc_root=Path('/proc'), drm_root=Path('/sys/class/drm')):
    clients = {}
    restricted = 0
    for process in proc_root.glob('[0-9]*'):
        try:
            pid = int(process.name)
            stat = (process / 'stat').read_text(errors='replace')
            started = stat.rsplit(')', 1)[1].split()[19]
            name = (process / 'comm').read_text(errors='replace').strip()
            descriptors = list((process / 'fd').iterdir())
        except (OSError, ValueError, IndexError):
            restricted += 1
            continue
        for descriptor in descriptors:
            try:
                link = os.readlink(descriptor)
                if not link.startswith('/dev/dri/'):
                    continue
                text = (process / 'fdinfo' / descriptor.name).read_text(errors='replace')[:65536]
                info = parse_fdinfo(text)
                sampled_at = time.monotonic_ns()
                if info is None:
                    continue
                device = (drm_root / Path(link).name / 'device').resolve()
                identity = info['device'] or pci(device.name) or 'platform:' + device.name
                if identity not in identities:
                    continue
                key = (identity, info['client'])
                owner = (pid, started, name)
                if key in clients:
                    clients[key]['owners'].add(owner)
                else:
                    clients[key] = {**info, 'owners': {owner}, 'sampleTimeNs': sampled_at}
            except OSError:
                restricted += 1
    return clients, restricted


def drm_tasks(cards, snapshot=drm_snapshot, sample_seconds=0.2):
    if not cards:
        return {}
    identities = {card['id'] for card in cards}
    before, denied1 = snapshot(identities)
    start = time.monotonic_ns()
    time.sleep(sample_seconds)
    after, denied2 = snapshot(identities)
    elapsed = max(1, time.monotonic_ns() - start)
    results = {identity: {'status': 'limited', 'rows': [], 'source': 'DRM fdinfo',
                         'usageLabel': 'Busiest engine',
                         'note': 'Only readable processes are shown. Memory is GPU buffers (system RAM on integrated GPUs); shared buffers can overlap.'} for identity in identities}
    process_rows = {}
    shared_owners = {}
    for (identity, client), info in after.items():
        prior = before.get((identity, client))
        owner = min(info['owners'])
        usage = None
        engine_usage = {}
        if prior and prior['owners'] & info['owners']:
            interval = max(1, info.get('sampleTimeNs', elapsed) - prior.get('sampleTimeNs', 0))
            values = []
            for engine, (counter, capacity) in info['engines'].items():
                previous = prior['engines'].get(engine)
                if previous and previous[1] == capacity and counter >= previous[0]:
                    engine_usage[engine] = min(100.0, (counter - previous[0]) / interval / capacity * 100)
                    values.append(engine_usage[engine])
            usage = max(values) if values else None
        row = task(owner[0], owner[2], 'DRM', info['memoryBytes'], usage, info['memoryKind'])
        row['sharedWith'] = sorted({item[0] for item in info['owners'] if item[0] != owner[0]})
        if row['sharedWith']:
            row['note'] = 'Shared DRM client; counters shown once'
        key = (identity, owner[0])
        existing = process_rows.get(key)
        if existing:
            if row['memoryBytes'] is not None:
                if existing['memoryBytes'] is not None and existing['memoryKind'] != row['memoryKind']:
                    existing['memoryKind'] = 'GPU buffers (mixed memory scopes)'
                existing['memoryBytes'] = (existing['memoryBytes'] or 0) + row['memoryBytes']
            for engine, value in engine_usage.items():
                existing['_engines'][engine] = min(100.0, existing['_engines'].get(engine, 0) + value)
            existing['gpuUsage'] = max(existing['_engines'].values()) if existing['_engines'] else None
            existing['sharedWith'] = sorted(set(existing['sharedWith'] + row['sharedWith']))
            existing['note'] = 'Unique DRM-client allocations summed; shared buffers may overlap'
        else:
            row['_engines'] = engine_usage
            process_rows[key] = row
        for shared in info['owners']:
            if shared[0] != owner[0]:
                shared_owners[(identity, shared[0])] = (shared, owner[0])
    for (identity, pid), row in process_rows.items():
        row.pop('_engines', None)
        results[identity]['rows'].append(row)
    for (identity, pid), (owner, primary) in shared_owners.items():
        if (identity, pid) not in process_rows:
            extra = task(pid, owner[2], 'Shared DRM')
            extra['note'] = f'Shares client counters shown on PID {primary}'
            results[identity]['rows'].append(extra)
    if denied1 or denied2:
        for result in results.values():
            result['note'] += ' Some processes are restricted or exited during sampling.'
    return results


def collect_processes(cards, run):
    nvidia = [card for card in cards if card.get('driverBackend') == 'nvidia-smi']
    others = [card for card in cards if card.get('driverBackend') != 'nvidia-smi']
    results = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [(pool.submit(nvidia_tasks, nvidia, run), nvidia),
                (pool.submit(drm_tasks, others), others)]
        for job, group in jobs:
            try:
                results.update(job.result())
            except Exception:
                for card in group:
                    results[card['id']] = {'status': 'unavailable', 'rows': [],
                        'note': 'This driver process source is temporarily unavailable', 'usageLabel': 'GPU activity'}
    for card in cards:
        card['processInfo'] = results.get(card['id'], {'status': 'unavailable', 'rows': [], 'note': 'Process telemetry unavailable', 'usageLabel': 'GPU activity'})
        card['processInfo']['rows'].sort(key=lambda row: (-(row['memoryBytes'] if row['memoryBytes'] is not None else -1), row['pid']))
