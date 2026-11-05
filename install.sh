#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v kpackagetool5 >/dev/null || { echo 'KDE Plasma 5 and kpackagetool5 are required.' >&2; exit 1; }
# Preserve any installed version before an explicit install/update.
stamp=$(date +%Y%m%d-%H%M%S)-$$
backup="$HOME/.local/state/plasma-gpu-vram-monitor/backups/$stamp"
data_home=${XDG_DATA_HOME:-$HOME/.local/share}
applet="$data_home/plasma/plasmoids/local.gpu.monitor"
mkdir -p "$backup" "$HOME/.local/bin"
if [ -d "$applet" ]; then cp -a "$applet" "$backup/"; fi
if [ -e "$HOME/.local/bin/gpu-panel-data" ]; then cp -a "$HOME/.local/bin/gpu-panel-data" "$backup/"; fi
if [ -e "$HOME/.local/bin/gpu_tasks.py" ]; then cp -a "$HOME/.local/bin/gpu_tasks.py" "$backup/"; fi
install -m 644 "$root/bin/gpu_tasks.py" "$HOME/.local/bin/gpu_tasks.py"
install -m 755 "$root/bin/gpu-panel-data" "$HOME/.local/bin/gpu-panel-data"
if [ -d "$applet" ]; then
    kpackagetool5 --type Plasma/Applet --upgrade "$root/plasmoid"
else
    kpackagetool5 --type Plasma/Applet --install "$root/plasmoid"
fi
printf 'Installed. Backups: %s\nAdd “GPU & VRAM Monitor” from Plasma Add Widgets.\n' "$backup"
