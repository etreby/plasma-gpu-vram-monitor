#!/usr/bin/env python3
"""Read-only multi-vendor GPU telemetry and opt-in diagnostic reports."""
import argparse
import csv
import io
import json
import math
from pathlib import Path
import platform
import subprocess
import time

PCI_ROOT = Path('/sys/bus/pci/devices')
CACHE = Path('/run/gpu-vram-monitor/temperatures.json')
VERSION = '1.3.0'


def run(args):
    return subprocess.check_output(args, text=True, timeout=8, stderr=subprocess.PIPE)


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def cache_sample(path=None, now=None):
    try:
        data = json.loads((path or CACHE).read_text())
        age = (time.time() if now is None else now) - data['timestamp']
        if data.get('schema') != 1 or not 0 <= age <= 15:
            return {}
        return data if isinstance(data.get('cards'), dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def temperatures(path=None, now=None):
    return cache_sample(path, now).get('cards', {})


def thermal(value):
    if isinstance(value, bool):
        return None
    value = number(value)
    return value if value is not None and 0 < value < 127 else None


def percentage(value):
    value = number(value)
    return value if value is not None and 0 <= value <= 100 else None


def nvidia_cards(cached):
    try:
        output = run([
            'nvidia-smi',
            '--query-gpu=index,name,pci.bus_id,memory.used,memory.total,utilization.gpu,utilization.memory,temperature.gpu,temperature.memory',
            '--format=csv,noheader,nounits',
        ])
    except (OSError, subprocess.SubprocessError):
        return []
    cards = []
    vendors = {'0x3842': 'EVGA', '0x19da': 'ZOTAC', '0x1043': 'ASUS',
               '0x1462': 'MSI', '0x1458': 'Gigabyte'}
    for raw in csv.reader(io.StringIO(output)):
        if len(raw) != 9:
            continue
        row = [v.strip() for v in raw]
        try:
            index = int(row[0])
        except ValueError:
            continue
        bdf = row[2][-12:].lower()
        vendor = read(PCI_ROOT / bdf / 'subsystem_vendor')
        t = cached.get(bdf, {})
        if not isinstance(t, dict):
            t = {}
        brand = vendors.get(vendor, '')
        name = (brand + ' ' + row[1].removeprefix('NVIDIA ').removeprefix('GeForce ')).strip()
        driver_vram, cached_vram = thermal(row[8]), thermal(t.get('vram'))
        junction = thermal(t.get('junction'))
        tier = t.get('support', 'legacy-cache')
        if tier not in ('verified', 'experimental', 'legacy-cache'):
            tier = 'unavailable'
        cards.append({
            'index': index, 'id': bdf, 'vendor': 'NVIDIA', 'name': name,
            'core': thermal(row[7]), 'junction': junction,
            'vram': driver_vram if driver_vram is not None else cached_vram,
            'used': number(row[3]), 'total': number(row[4]),
            'load': percentage(row[5]), 'memoryLoad': percentage(row[6]),
            'thermalSupport': tier if junction is not None or cached_vram is not None else
                              ('driver-provided' if driver_vram is not None else 'unavailable'),
            'temperatureSources': {'core': 'nvidia-smi',
                'junction': tier + '-register-cache' if junction is not None else None,
                'vram': 'nvidia-smi' if driver_vram is not None else
                        tier + '-register-cache' if cached_vram is not None else None},
        })
    return cards


def hwmon_temperatures(device, driver):
    readings = {'core': None, 'junction': None, 'vram': None}
    labels = {'edge': 'core', 'gpu': 'core', 'core': 'core',
              'junction': 'junction', 'hotspot': 'junction',
              'mem': 'vram', 'memory': 'vram', 'vram': 'vram'}
    for hwmon in sorted((device / 'hwmon').glob('hwmon*')):
        # Ignore third-party bridges and CPU/package sensors near a GPU device.
        if read(hwmon / 'name') not in ('amdgpu', 'i915', 'xe'):
            continue
        for channel in sorted(hwmon.glob('temp*_input')):
            stem = channel.name.removesuffix('_input')
            if read(hwmon / (stem + '_fault')) == '1':
                continue
            label = read(hwmon / (stem + '_label'))
            target = labels.get(label.lower()) if label else ('core' if stem == 'temp1' else None)
            if target is None:
                continue
            value = number(read(channel))
            readings[target] = thermal(value / 1000) if value is not None else None
    return readings


def sysfs_cards(pci_root=None):
    cards = []
    for device in sorted((pci_root or PCI_ROOT).glob('*')):
        vendor = read(device / 'vendor')
        if vendor not in ('0x1002', '0x8086'):
            continue
        try:
            if int(read(device / 'class') or '0', 16) >> 16 != 0x03:
                continue
        except ValueError:
            continue
        driver = (device / 'driver').resolve().name
        if driver not in ('amdgpu', 'i915', 'xe'):
            continue
        status = read(device / 'power/runtime_status')
        if status not in ('active', None):
            continue
        temps = hwmon_temperatures(device, driver)
        used = number(read(device / 'mem_info_vram_used')) if driver == 'amdgpu' else None
        total = number(read(device / 'mem_info_vram_total')) if driver == 'amdgpu' else None
        load = percentage(read(device / 'gpu_busy_percent')) if driver == 'amdgpu' else None
        memory_load = percentage(read(device / 'mem_busy_percent')) if driver == 'amdgpu' else None
        if all(value is None for value in (*temps.values(), used, total, load, memory_load)):
            continue
        brand = 'AMD' if vendor == '0x1002' else 'Intel'
        model = (read(device / 'device') or '').removeprefix('0x')
        cards.append({'index': 0, 'id': device.name, 'vendor': brand,
                      'name': f'{brand} GPU {model}', **temps,
                      'used': used / 1048576 if used is not None and used >= 0 else None,
                      'total': total / 1048576 if total is not None and total > 0 else None,
                      'load': load, 'memoryLoad': memory_load,
                      'thermalSupport': 'driver-provided',
                      'temperatureSources': {key: 'hwmon' if value is not None else None
                                             for key, value in temps.items()}})
    return cards


def collect():
    cards = nvidia_cards(temperatures()) + sysfs_cards()
    if not cards:
        raise RuntimeError('No readable GPU telemetry')
    cards.sort(key=lambda card: card['id'])
    for index, card in enumerate(cards):
        card['index'] = index
    return {'ok': True, 'timestamp': time.time(), 'cards': cards}


def diagnose(pci_root=None):
    # Explicit whitelist: no hostname, username, serial, UUID, process or environment data.
    inventory = []
    for device in sorted((pci_root or PCI_ROOT).glob('*')):
        try:
            if int(read(device / 'class') or '0', 16) >> 16 != 0x03:
                continue
        except ValueError:
            continue
        inventory.append({'pci': device.name, 'vendor_id': read(device / 'vendor'),
                          'device_id': read(device / 'device'),
                          'subsystem_vendor_id': read(device / 'subsystem_vendor'),
                          'subsystem_device_id': read(device / 'subsystem_device'),
                          'driver': (device / 'driver').resolve().name,
                          'runtime_status': read(device / 'power/runtime_status')})
    try:
        telemetry = collect()
    except Exception:
        telemetry = {'ok': False, 'cards': []}
    register_support = {}
    support = cache_sample().get('support', {})
    if isinstance(support, dict):
        for bdf, profile in support.items():
            if isinstance(profile, dict):
                register_support[bdf] = {key: profile.get(key) for key in ('device_id', 'tier', 'enabled', 'profile')}
    return {'report_schema': 1, 'widget_version': VERSION, 'kernel': platform.release(),
            'nvidia_driver': read(Path('/sys/module/nvidia/version')),
            'inventory': inventory, 'telemetry': telemetry, 'register_support': register_support,
            'notice': 'Generated locally; review before sharing. No data is uploaded.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnose', action='store_true', help='Print a local, privacy-filtered tester report; never upload')
    args = parser.parse_args(argv)
    if args.diagnose:
        print(json.dumps(diagnose(), allow_nan=False, indent=2))
        return
    try:
        sample = collect()
    except Exception:
        sample = {'ok': False, 'error': 'GPU readings unavailable. Check GPU drivers and readable sysfs sensors.'}
    print(json.dumps(sample, allow_nan=False))


if __name__ == '__main__':
    main()
