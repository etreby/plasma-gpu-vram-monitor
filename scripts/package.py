#!/usr/bin/env python3
"""Build the Plasma archive and the complete source/installer bundle."""
from pathlib import Path
import hashlib
import tarfile
import zipfile

root = Path(__file__).resolve().parents[1]
out = root / 'dist'
out.mkdir(exist_ok=True)
version = '1.3.0'
with zipfile.ZipFile(out / f'gpu-vram-monitor-{version}.plasmoid', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((root / 'plasmoid').rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(root / 'plasmoid'))
with tarfile.open(out / f'plasma-gpu-vram-monitor-{version}.tar.gz', 'w:gz') as archive:
    for name in ('README.md', 'LICENSE', 'install.sh', 'bin', 'plasmoid', 'scripts', 'tests', 'docs', 'sensors'):
        archive.add(root / name, arcname=f'plasma-gpu-vram-monitor-{version}/{name}',
                    filter=lambda info: None if '__pycache__' in info.name or info.name.endswith('.pyc') else info)
assets = [out / f'gpu-vram-monitor-{version}.plasmoid', out / f'plasma-gpu-vram-monitor-{version}.tar.gz']
(out / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets))
for path in assets:
    print(path.name)
