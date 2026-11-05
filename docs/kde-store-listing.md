# KDE Store submission

Submission page: https://store.kde.org/product/add

Name: GPU & VRAM Monitor (Plasma 5)

Category: Plasma 5 widget / Plasmoid category (choose the current equivalent in the form; not Plasma 6).

License: GPL-3.0

Version: 1.2.0

Source / homepage: https://github.com/etreby/plasma-gpu-vram-monitor

Download file: gpu-vram-monitor-1.2.0.plasmoid from the GitHub v1.2.0 release.

## Description

Monitor NVIDIA GPU core and VRAM temperatures, GPU load, and used/total VRAM
from a compact KDE Plasma panel widget. Hover for hotspot temperature and memory
activity. Supports multiple cards, follows Plasma theme colors, and refreshes
every three seconds. Unavailable readings and stale samples are marked clearly.

**Requires KDE Plasma 5.27, Python 3.9+ and NVIDIA's nvidia-smi.
Plasma 6 is not supported.**

The bundled Python helper provides GPU core temperature, load and VRAM usage.
For RTX 3090 VRAM/hotspot temperatures, install the included optional system
sensor service from the source bundle (sudo ./sensors/install.sh). This newly
authored service reads fixed PCI registers with Python's standard library and
publishes a cache; the widget runs unprivileged. No external gputemps tool,
libpci, third-party Python packages or DKMS module is required. Direct register
support is currently limited to PCI device 10de:2204. Unsupported channels show
a dash; kernel restrictions can prevent register access. See the README and
reader provenance notes for details.

Originally tested with two NVIDIA RTX 3090 cards. GPL-3.0.

## Submission status

Not submitted. The KDE Store submission page returned Anubis Access Denied in
the automation browser on 2026-11-05. A signed-in user browser is needed to
complete the listing. Screenshots for the listing are available in docs/screenshots/gpu-widget.png
and docs/screenshots/top-panel.png. They show the polished live widget. The expanded view is in
docs/screenshots/details.png.
