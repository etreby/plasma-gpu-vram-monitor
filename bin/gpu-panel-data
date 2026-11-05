#!/usr/bin/env python3
"""Read-only JSON telemetry for the Plasma 5 GPU panel applet."""
import csv
import io
import json
import math
from pathlib import Path
import subprocess
import time


def run(args):
    return subprocess.check_output(args, text=True, timeout=8, stderr=subprocess.PIPE)


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


CACHE = Path('/run/gpu-vram-monitor/temperatures.json')


def temperatures(path=None, now=None):
    try:
        data = json.loads((path or CACHE).read_text())
        age = (time.time() if now is None else now) - data['timestamp']
        if data.get('schema') != 1 or not 0 <= age <= 15:
            return {}
        return data['cards'] if isinstance(data['cards'], dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def thermal(value):
    if isinstance(value, bool):
        return None
    value = number(value)
    return value if value is not None and 0 < value < 127 else None


def collect():
    cached = temperatures()
    rows = csv.reader(io.StringIO(run([
        'nvidia-smi',
        '--query-gpu=index,name,pci.bus_id,memory.used,memory.total,utilization.gpu,utilization.memory,temperature.gpu,temperature.memory',
        '--format=csv,noheader,nounits',
    ])))
    usage = {int(r[0]): [v.strip() for v in r] for r in rows}
    cards = []
    vendors = {'0x3842': 'EVGA', '0x19da': 'ZOTAC', '0x1043': 'ASUS',
               '0x1462': 'MSI', '0x1458': 'Gigabyte'}
    for index, row in usage.items():
        bdf = row[2][-12:].lower()
        try:
            vendor = Path('/sys/bus/pci/devices', bdf, 'subsystem_vendor').read_text().strip()
        except OSError:
            vendor = ''
        t = cached.get(bdf, {})
        if not isinstance(t, dict):
            t = {}
        brand = vendors.get(vendor, '')
        name = (brand + ' ' + row[1].removeprefix('NVIDIA ').removeprefix('GeForce ')).strip()
        cards.append({
            'index': index, 'name': name,
            'core': thermal(row[7]), 'junction': thermal(t.get('junction')),
            'vram': thermal(row[8]) if thermal(row[8]) is not None else thermal(t.get('vram')), 'used': number(row[3]),
            'total': number(row[4]), 'load': number(row[5]), 'memoryLoad': number(row[6]),
        })
    if not cards:
        raise RuntimeError('No matching GPU readings')
    return {'ok': True, 'timestamp': time.time(), 'cards': sorted(cards, key=lambda c: c['index'])}


def main():
    try:
        sample = collect()
    except Exception:
        sample = {'ok': False, 'error': 'GPU readings unavailable. Check nvidia-smi and the gpu-vram-monitor-sensors service.'}
    print(json.dumps(sample, allow_nan=False))


if __name__ == '__main__':
    main()
