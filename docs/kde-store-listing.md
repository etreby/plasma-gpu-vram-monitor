# KDE Store submission

Submission page: https://store.kde.org/product/add

Name: GPU & VRAM Monitor (Plasma 5)

Category: Plasma 5 widget / Plasmoid category (choose the current equivalent in the form; not Plasma 6).

License: GPL-3.0

Version: 1.0.1

Source / homepage: https://github.com/etreby/plasma-gpu-vram-monitor

Download file: gpu-vram-monitor-1.0.1.plasmoid from the GitHub v1.0.1 release.

## Description

Monitor NVIDIA GPU core and VRAM temperatures, GPU load, and used/total VRAM
from a compact KDE Plasma panel widget. Hover for hotspot temperature and memory
activity. Supports multiple cards, follows Plasma theme colors, and refreshes
every three seconds. Unavailable readings and stale samples are marked clearly.

**Requires KDE Plasma 5.27, Python 3.9+, NVIDIA's nvidia-smi, and a separately
installed gputemps reader supporting --once --json. Plasma 6 is not supported.**

The Python helper is included in the widget archive. The gputemps reader is not
bundled and must already work noninteractively as your desktop user. Its
hardware support and access requirements apply. See the project README for
setup and troubleshooting. This widget does not configure privileged access or
change GPU fans, clocks, desktop themes, or panel layouts.

Originally tested with two NVIDIA RTX 3090 cards. GPL-3.0.

## Submission status

Not submitted. The KDE Store submission page returned Anubis Access Denied in
the automation browser on 2026-11-05. A signed-in user browser is needed to
complete the listing. Add a real screenshot of the widget when submitting.
