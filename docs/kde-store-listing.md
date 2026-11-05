# KDE Store submission

Submission page: https://store.kde.org/product/add

Name: GPU & VRAM Monitor (Plasma 5)

Category: Plasma 5 widget / Plasmoid category (choose the current equivalent in the form; not Plasma 6).

License: GPL-3.0

Version: 1.4.0

Source / homepage: https://github.com/etreby/plasma-gpu-vram-monitor

Download file: gpu-vram-monitor-1.4.0.plasmoid from the GitHub v1.4.0 release.

## Description

Monitor GPU core and VRAM temperatures, GPU load, and used/total VRAM
from a compact KDE Plasma panel widget. Hover for hotspot temperature and memory
activity. Supports multiple cards, follows Plasma theme colors, and refreshes
every three seconds. Unavailable readings and stale samples are marked clearly.

**Requires KDE Plasma 5.27 and Python 3.9+. Plasma 6 is not supported.**

NVIDIA uses nvidia-smi. AMD uses readable amdgpu sysfs/hwmon sensors; Intel uses
GPU hwmon temperatures only where exposed. Legacy Radeon, Nouveau and other
GPU-attached driver hwmon sensors are read when available. PCI/DRM discovery
includes cards without readable sensors and lists them with their status.
Detection does not imply full telemetry or VRAM-temperature support on every GPU. Unsupported readings show a dash.

The optional bundled system service provides verified RTX 3090 direct VRAM and
hotspot readings. Researched RTX 3080, 3080 Ti and 3090 Ti PCI IDs have experimental
profiles, disabled until an administrator explicitly opts in to each ID. Unknown
direct-register layouts remain blocked. AMD/Intel and experimental profiles have
synthetic tests, not real-card validation here. See docs/hardware-support.md for
the exact support matrix and instructions.

An unprivileged --diagnose command generates a local report without automatic
uploads; a GitHub hardware-report form supports community validation. No external
gputemps, libpci, third-party Python package or DKMS dependency is needed.

Originally tested with two NVIDIA RTX 3090 cards. GPL-3.0.

## Submission status

Not submitted. The KDE Store submission page returned Anubis Access Denied in
the automation browser on 2026-11-05. A signed-in user browser is needed to
complete the listing. Screenshots for the listing are available in docs/screenshots/gpu-widget.png
and docs/screenshots/top-panel.png. They show the polished live widget. The expanded view is in
docs/screenshots/details.png.
