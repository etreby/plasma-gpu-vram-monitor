#!/usr/bin/python3
"""Read-only allowlisted NVIDIA thermal sampling. No third-party Python modules.

SPDX-License-Identifier: GPL-3.0-only
Register facts and scope are documented in docs/sensor-reader.md.
"""
import argparse
import json
import mmap
import os
from pathlib import Path
import signal
import struct
import time

PCI_ROOT = Path('/sys/bus/pci/devices')
CACHE = Path('/run/gpu-vram-monitor/temperatures.json')
PROFILES = {
    0x2204: {'name': 'RTX 3090', 'tier': 'verified'},
    0x2203: {'name': 'RTX 3090 Ti', 'tier': 'experimental'},
    0x2206: {'name': 'RTX 3080', 'tier': 'experimental'},
    0x220A: {'name': 'RTX 3080', 'tier': 'experimental'},
    0x2216: {'name': 'RTX 3080', 'tier': 'experimental'},
    0x2208: {'name': 'RTX 3080 Ti', 'tier': 'experimental'},
}
REGISTERS = {'vram': 0xE2A8, 'junction': 0x2046C}


def decode(channel, raw):
    if raw == 0 or raw == 0xFFFFFFFF or raw >> 16 == 0xBADF:
        return None
    if channel == 'vram':
        value = (raw & 0xFFF) // 32
    elif channel == 'junction':
        value = (raw >> 8) & 0xFF
    else:
        raise ValueError('Unknown thermal channel')
    return value if 0 < value < 127 else None


def register_value(device, offset):
    # resource0 addresses this device's BAR0, not arbitrary physical RAM.
    # Only one page is mapped, with kernel-enforced read-only protection.
    page_offset, byte_offset = divmod(offset, mmap.PAGESIZE)
    with (device / 'resource0').open('rb', buffering=0) as resource:
        with mmap.mmap(resource.fileno(), mmap.PAGESIZE,
                       flags=mmap.MAP_SHARED, prot=mmap.PROT_READ,
                       offset=page_offset * mmap.PAGESIZE) as page:
            return struct.unpack_from('<I', page, byte_offset)[0]


def sample(pci_root=PCI_ROOT, experimental_devices=()):
    cards = {}
    errors = {}
    support = {}
    for device in sorted(pci_root.glob('*')):
        try:
            if int((device / 'vendor').read_text(), 16) != 0x10DE:
                continue
            device_id = int((device / 'device').read_text(), 16)
            if int((device / 'class').read_text(), 16) >> 16 != 0x03:
                continue
            profile = PROFILES.get(device_id)
            tier = profile['tier'] if profile else 'unsupported'
            enabled = tier == 'verified' or (tier == 'experimental' and device_id in experimental_devices)
            support[device.name] = {'device_id': f'{device_id:04x}', 'tier': tier,
                                    'enabled': enabled, 'profile': profile['name'] if profile else None}
            if not enabled:
                if tier == 'experimental':
                    errors[device.name] = 'Experimental profile disabled; explicit administrator opt-in required'
                continue
            if (device / 'driver').resolve().name != 'nvidia':
                continue
            if (device / 'power/runtime_status').read_text().strip() != 'active':
                errors[device.name] = 'GPU is suspended'
                continue
            resource_line = (device / 'resource').read_text().splitlines()[0].split()
            start, end, flags = (int(v, 16) for v in resource_line)
            if not start or end < start or not flags & 0x200 or end - start + 1 <= max(REGISTERS.values()) + 4:
                errors[device.name] = 'Invalid GPU register resource'
                continue
            # The output is matched by PCI address, never NVIDIA enumeration index.
            cards[device.name] = {channel: decode(channel, register_value(device, offset))
                                  for channel, offset in REGISTERS.items()}
            cards[device.name]['support'] = tier
            cards[device.name]['profile'] = profile['name']
        except (OSError, ValueError, IndexError, struct.error):
            errors[device.name] = 'Thermal registers unavailable'
    return {'schema': 1, 'timestamp': time.time(), 'cards': cards, 'errors': errors, 'support': support}


def publish(data, destination=CACHE):
    # Directory is root-owned; never follow a user-supplied output path.
    temporary = destination.with_suffix('.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'w') as out:
        json.dump(data, out, allow_nan=False)
        out.write('\n')
    os.replace(temporary, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Print a sample; do not write files')
    parser.add_argument('--experimental-device', action='append', default=[],
                        type=lambda value: int(value, 16),
                        choices=[key for key, profile in PROFILES.items() if profile['tier'] == 'experimental'],
                        help='Opt in to one researched PCI ID, e.g. 2206; repeat for multiple IDs')
    parser.add_argument('--verified-only', action='store_true', help='Explicitly disable all experimental profiles')
    parser.add_argument('--list-support', action='store_true', help='List profiles without accessing hardware')
    parser.add_argument('--validate-options', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.verified_only and args.experimental_device:
        parser.error('--verified-only cannot be combined with --experimental-device')
    if args.list_support:
        print(json.dumps({f'{key:04x}': profile for key, profile in PROFILES.items()}))
        return
    if args.validate_options:
        print(' '.join(f'--experimental-device={key:04x}' for key in sorted(set(args.experimental_device))))
        return
    if args.once:
        print(json.dumps(sample(experimental_devices=args.experimental_device), allow_nan=False))
        return
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        publish(sample(experimental_devices=args.experimental_device))
        # Short sleeps allow a prompt, graceful stop without stale cache reuse.
        for _ in range(30):
            if not running:
                break
            time.sleep(0.1)


if __name__ == '__main__':
    main()
