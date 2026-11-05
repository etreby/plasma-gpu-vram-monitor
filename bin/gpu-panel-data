#!/usr/bin/env python3
"""Read-only JSON telemetry for the Plasma 5 GPU panel applet."""
import csv
import io
import json
import math
import os
from pathlib import Path
import shutil
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


def collect():
    reader = os.environ.get('GPUTEMPS_COMMAND') or shutil.which('gputemps')
    if not reader and Path('/usr/local/bin/gputemps').is_file():
        reader = '/usr/local/bin/gputemps'
    if not reader:
        raise RuntimeError('gputemps is not installed')
    temps = json.loads(run([reader, '--once', '--json']))
    rows = csv.reader(io.StringIO(run([
        'nvidia-smi',
        '--query-gpu=index,name,pci.bus_id,memory.used,memory.total,utilization.gpu,utilization.memory',
        '--format=csv,noheader,nounits',
    ])))
    usage = {int(r[0]): [v.strip() for v in r] for r in rows}
    cards = []
    vendors = {'0x3842': 'EVGA', '0x19da': 'ZOTAC', '0x1043': 'ASUS',
               '0x1462': 'MSI', '0x1458': 'Gigabyte'}
    for t in temps['gpus']:
        row = usage.get(int(t['index']))
        if row is None:
            continue
        bdf = row[2][-12:].lower()
        try:
            vendor = Path('/sys/bus/pci/devices', bdf, 'subsystem_vendor').read_text().strip()
        except OSError:
            vendor = ''
        brand = vendors.get(vendor, '')
        name = (brand + ' ' + row[1].removeprefix('NVIDIA ').removeprefix('GeForce ')).strip()
        cards.append({
            'index': int(t['index']), 'name': name,
            'core': number(t.get('core')), 'junction': number(t.get('junction')),
            'vram': number(t.get('vram')), 'used': number(row[3]),
            'total': number(row[4]), 'load': number(row[5]), 'memoryLoad': number(row[6]),
        })
    if not cards:
        raise RuntimeError('No matching GPU readings')
    return {'ok': True, 'timestamp': time.time(), 'cards': sorted(cards, key=lambda c: c['index'])}


def main():
    try:
        sample = collect()
    except Exception:
        sample = {'ok': False, 'error': 'GPU readings unavailable. Check gputemps --once --json and nvidia-smi.'}
    print(json.dumps(sample, allow_nan=False))


if __name__ == '__main__':
    main()
