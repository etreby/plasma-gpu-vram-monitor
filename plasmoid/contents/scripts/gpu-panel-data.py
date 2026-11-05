#!/usr/bin/env python3
"""Read-only multi-vendor GPU telemetry and opt-in diagnostic reports."""
import argparse
import csv
import io
import json
import math
from pathlib import Path
import platform
import re
import xml.etree.ElementTree as ET
import subprocess
import time

PCI_ROOT = Path('/sys/bus/pci/devices')
CACHE = Path('/run/gpu-vram-monitor/temperatures.json')
VERSION = '1.4.0'
DRM_ROOT = Path('/sys/class/drm')


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


def canonical_pci(value):
    match = re.fullmatch(r'([0-9a-fA-F]{4,8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])', value)
    if not match or int(match[1], 16) > 0xffff:
        return None
    return f'{int(match[1], 16):04x}:{match[2].lower()}:{match[3].lower()}.{match[4]}'


def nvidia_rows():
    try:
        output = run([
            'nvidia-smi',
            '--query-gpu=index,name,pci.bus_id,memory.used,memory.total,utilization.gpu,utilization.memory,temperature.gpu,temperature.memory',
            '--format=csv,noheader,nounits',
        ])
        rows = list(csv.reader(io.StringIO(output)))
        if any(len(row) == 9 for row in rows):
            return rows
    except (OSError, subprocess.SubprocessError):
        pass
    # Older drivers can reject the optional memory-temperature query entirely.
    # XML keeps per-field N/A values independent and avoids model whitelists.
    try:
        tree = ET.fromstring(run(['nvidia-smi', '-q', '-x']))
    except (OSError, subprocess.SubprocessError, ET.ParseError):
        return []
    rows = []
    for index, gpu in enumerate(tree.findall('gpu')):
        def field(name):
            value = gpu.findtext(name, 'N/A').strip()
            return (value.split()[0] if value.split() else 'N/A') if name != 'product_name' else value
        rows.append([str(index), field('product_name'), field('pci/pci_bus_id'),
                     field('fb_memory_usage/used'), field('fb_memory_usage/total'),
                     field('utilization/gpu_util'), field('utilization/memory_util'),
                     field('temperature/gpu_temp'), field('temperature/memory_temp')])
    return rows


def nvidia_cards(cached):
    cards = []
    vendors = {'0x3842': 'EVGA', '0x19da': 'ZOTAC', '0x1043': 'ASUS',
               '0x1462': 'MSI', '0x1458': 'Gigabyte'}
    for raw in nvidia_rows():
        if len(raw) != 9:
            continue
        row = [v.strip() for v in raw]
        try:
            index = int(row[0])
        except ValueError:
            continue
        bdf = canonical_pci(row[2])
        if bdf is None:
            continue
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
                              ('driver-provided' if driver_vram is not None or thermal(row[7]) is not None else 'unavailable'),
            'temperatureSources': {'core': 'nvidia-smi',
                'junction': tier + '-register-cache' if junction is not None else None,
                'vram': 'nvidia-smi' if driver_vram is not None else
                        tier + '-register-cache' if cached_vram is not None else None},
        })
    return cards


def discover_gpus(pci_root=None, drm_root=None):
    devices = {}
    for device in sorted((pci_root or PCI_ROOT).glob('*')):
        try:
            if int(read(device / 'class') or '0', 16) >> 16 != 0x03:
                continue
        except ValueError:
            continue
        devices[str(device.resolve())] = (device.name, device)
    for card in sorted((drm_root or DRM_ROOT).glob('card*')):
        if not re.fullmatch(r'card[0-9]+', card.name) or not (card / 'device').exists():
            continue
        device = (card / 'device').resolve()
        devices.setdefault(str(device), (canonical_pci(device.name) or 'platform:' + device.name, device))
    result = []
    vendors = {'0x1002': 'AMD', '0x10de': 'NVIDIA', '0x8086': 'Intel',
               '0x13b5': 'ARM', '0x17cb': 'Qualcomm', '0x14e4': 'Broadcom',
               '0x106b': 'Apple', '0x15ad': 'VMware', '0x1af4': 'Virtio'}
    for identity, device in devices.values():
        driver = (device / 'driver').resolve().name if (device / 'driver').exists() else None
        vendor_id = read(device / 'vendor')
        vendor = vendors.get(vendor_id, driver or 'Unknown')
        model = (read(device / 'device') or identity.removeprefix('platform:')).removeprefix('0x')
        result.append({'id': identity, 'path': device, 'vendor': vendor,
                       'name': f'{vendor} GPU {model}', 'driver': driver,
                       'runtime_status': read(device / 'power/runtime_status')})
    return sorted(result, key=lambda device: device['id'])


def hwmon_temperatures(device, driver):
    readings = {'core': None, 'junction': None, 'vram': None}
    labels = {'edge': 'core', 'gpu': 'core', 'core': 'core', 'gpu core': 'core',
              'junction': 'junction', 'hotspot': 'junction', 'gpu hotspot': 'junction',
              'mem': 'vram', 'memory': 'vram', 'vram': 'vram', 'gpu memory': 'vram'}
    for hwmon in sorted((device / 'hwmon').glob('hwmon*')):
        name = read(hwmon / 'name')
        # A CPU sensor or third-party bridge must never masquerade as this GPU.
        trusted = name == driver or (driver == 'nouveau' and name in ('nouveau', 'nvkm'))
        if not trusted:
            continue
        for channel in sorted(hwmon.glob('temp*_input')):
            stem = channel.name.removesuffix('_input')
            if read(hwmon / (stem + '_fault')) == '1' or read(hwmon / (stem + '_enable')) == '0':
                continue
            label = read(hwmon / (stem + '_label'))
            normalized = label.lower().strip() if label else ''
            target = labels.get(normalized)
            if normalized in ('package', 'gpu package') and driver in ('i915', 'xe'):
                target = 'core'  # GPU package, from GPU-attached i915/xe hwmon.
            if not normalized and stem == 'temp1' and driver in ('amdgpu', 'radeon', 'nouveau', 'i915', 'xe'):
                target = 'core'
            if target is None:
                continue
            value = number(read(channel))
            readings[target] = thermal(value / 1000) if value is not None else None
    return readings


def sysfs_cards(pci_root=None, devices=None):
    cards = []
    for gpu in devices if devices is not None else discover_gpus(pci_root):
        device, driver = gpu['path'], gpu['driver']
        if not driver or gpu['runtime_status'] not in ('active', None):
            continue
        temps = hwmon_temperatures(device, driver)
        used = number(read(device / 'mem_info_vram_used')) if driver == 'amdgpu' else None
        total = number(read(device / 'mem_info_vram_total')) if driver == 'amdgpu' else None
        load = percentage(read(device / 'gpu_busy_percent')) if driver == 'amdgpu' else None
        memory_load = percentage(read(device / 'mem_busy_percent')) if driver == 'amdgpu' else None
        if all(value is None for value in (*temps.values(), used, total, load, memory_load)):
            continue
        cards.append({'index': 0, 'id': gpu['id'], 'vendor': gpu['vendor'],
                      'name': gpu['name'], **temps,
                      'used': used / 1048576 if used is not None and used >= 0 else None,
                      'total': total / 1048576 if total is not None and total > 0 else None,
                      'load': load, 'memoryLoad': memory_load,
                      'thermalSupport': 'driver-provided',
                      'temperatureSources': {key: 'hwmon' if value is not None else None
                                             for key, value in temps.items()}})
    return cards


METRICS = ('core', 'junction', 'vram', 'used', 'total', 'load', 'memoryLoad')


def collect():
    devices = discover_gpus()
    merged = {card['id']: card for card in sysfs_cards(devices=devices)}
    for card in nvidia_cards(temperatures()):
        base = merged.get(card['id'])
        if base:
            for metric in METRICS:
                if card[metric] is None:
                    card[metric] = base[metric]
                    if metric in card['temperatureSources'] and base[metric] is not None:
                        card['temperatureSources'][metric] = 'hwmon'
                        if card['thermalSupport'] == 'unavailable':
                            card['thermalSupport'] = 'driver-provided'
        merged[card['id']] = card
    inventory = []
    for gpu in devices:
        card = merged.get(gpu['id'])
        available = [key for key in METRICS if card and card[key] is not None]
        status = 'available' if available else 'suspended' if gpu['runtime_status'] not in ('active', None) else 'no-driver' if not gpu['driver'] else 'no-readable-sensors'
        inventory.append({key: gpu[key] for key in ('id', 'name', 'vendor', 'driver', 'runtime_status')} |
                         {'status': status, 'available_metrics': available})
    cards = sorted(merged.values(), key=lambda card: card['id'])
    for index, card in enumerate(cards):
        card['index'] = index
        card['capabilities'] = {key: card[key] is not None for key in METRICS}
        card['missingMetrics'] = {key: 'Not exposed by the driver or no enabled compatible thermal profile'
                                  for key in METRICS if card[key] is None}
    if not cards and not inventory:
        raise RuntimeError('No GPU devices discovered')
    return {'ok': True, 'timestamp': time.time(), 'cards': cards, 'devices': inventory,
            'message': 'No readable GPU sensors; open details for detected devices' if not cards else ''}


def diagnose(pci_root=None):
    # Explicit whitelist: no hostname, username, serial, UUID, process or environment data.
    inventory = []
    for gpu in discover_gpus(pci_root):
        device = gpu['path']
        inventory.append({'id': gpu['id'], 'vendor_id': read(device / 'vendor'),
                          'device_id': read(device / 'device'),
                          'subsystem_vendor_id': read(device / 'subsystem_vendor'),
                          'subsystem_device_id': read(device / 'subsystem_device'),
                          'driver': gpu['driver'], 'runtime_status': gpu['runtime_status']})
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
