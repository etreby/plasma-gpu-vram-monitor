#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'Run this installer with sudo.' >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
backup="/var/backups/gpu-vram-monitor/$(date +%Y%m%d-%H%M%S)-$$"
install -d -m 700 "$backup"
for file in /usr/local/libexec/gpu-vram-monitor-sensors /etc/systemd/system/gpu-vram-monitor-sensors.service; do
    if [ -e "$file" ]; then cp -a "$file" "$backup/"; fi
done
install -o root -g root -m 755 "$root/gpu-vram-sensors.py" /usr/local/libexec/gpu-vram-monitor-sensors
install -o root -g root -m 644 "$root/gpu-vram-monitor-sensors.service" /etc/systemd/system/gpu-vram-monitor-sensors.service
systemctl daemon-reload
systemctl enable gpu-vram-monitor-sensors.service
systemctl restart gpu-vram-monitor-sensors.service
printf 'Temperature service installed. Backups: %s\n' "$backup"
