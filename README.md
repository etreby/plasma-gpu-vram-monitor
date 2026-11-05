# GPU & VRAM Monitor for KDE Plasma 5

A compact panel widget showing NVIDIA GPU core and VRAM temperatures, GPU load,
and used/total VRAM. Hover for hotspot temperature and memory activity. Updates
every three seconds, supports multiple GPUs, follows Plasma theme colors, and
marks unavailable or stale readings. Originally used with two RTX 3090 cards.

## Requirements

- Linux with **KDE Plasma 5.27**, Python 3.9+, and `kpackagetool5`.
- NVIDIA proprietary driver with `nvidia-smi` available.
- [gputemps](https://github.com/ThomasBaruzier/gddr6-core-junction-vram-temps)
  supporting `--once --json`, accessible noninteractively as your desktop user.
  The widget reads `index`, `core`, `junction`, and `vram` from its `gpus` array.
  Actual temperature support depends on your GPU and the reader.

This release targets Plasma 5's executable data engine. **Plasma 6 is not
supported.** The widget does not install drivers, change fans/clocks, or set up
privileged access. The separate gputemps reader accesses undocumented hardware
registers and can require root access. If using a sudo wrapper, keep the reader
and its parent directories root-owned and allow only that executable; never
permit an ordinary-user-writable program to run as root. No privileged reader
or sudoers rule is included here.

## Install

Download and extract the source `.tar.gz` from Releases, then run:

```sh
cd plasma-gpu-vram-monitor-1.0.0
./install.sh
```

The installer backs up any existing applet/helper under
`~/.local/state/plasma-gpu-vram-monitor/backups/`, installs the Python helper in
`~/.local/bin`, and installs or upgrades the applet. Add **GPU & VRAM Monitor**
through Plasma's **Add Widgets** menu. It does not modify panel layouts, themes,
or restart your desktop. An existing applet may require your next login to pick
up changed QML. The applet ID remains `local.gpu.monitor` for existing users.

The standalone `.plasmoid` archive can also be installed with
`kpackagetool5 --type Plasma/Applet --install gpu-vram-monitor-1.0.0.plasmoid`;
it still requires `bin/gpu-panel-data` installed as `~/.local/bin/gpu-panel-data`.
Use the full source installer for both components.

## Troubleshooting

Run these as your normal desktop user:

```sh
gputemps --once --json
nvidia-smi
~/.local/bin/gpu-panel-data
```

The helper must return JSON with `ok: true`. Missing readings display a dash.
The helper finds gputemps on PATH or at `/usr/local/bin/gputemps`. You can set
`GPUTEMPS_COMMAND` in the Plasma session environment to an absolute executable
path (no arguments). Each subprocess has an eight-second timeout. It returns a
safe error message instead of subprocess stderr. GPU indices join simultaneous
reader and NVIDIA samples; vendor labels come from PCI subsystem vendor IDs,
with no machine-specific UUIDs stored in the source. A driver reset or device
change can temporarily make readings unavailable.

## Remove

```sh
kpackagetool5 --type Plasma/Applet --remove local.gpu.monitor
rm ~/.local/bin/gpu-panel-data
```

Remove the widget from the panel first. Keep any independent gputemps reader or
hwmon bridge if other programs use it. Backups remain available for restoration.

## Development and packages

```sh
python3 -m unittest discover -s tests -v
sh -n install.sh
python3 scripts/package.py
```

`dist/` contains a `.plasmoid`, complete source/installer `.tar.gz`, and SHA-256
checksums. GPL-3.0; see LICENSE. gputemps and KDE are independent upstream
projects and are not bundled.
