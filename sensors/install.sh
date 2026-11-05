#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'Run this installer with sudo.' >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# Accept only explicit opt-ins; validation uses the reader's profile allowlist.
# No arguments preserves a previous administrator-managed opt-in drop-in.
configure=0
for arg in "$@"; do
    case "$arg" in
        --experimental-device|--experimental-device=*|--verified-only|0x*|[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]) ;;
        *) echo 'Use --experimental-device 2206 (repeatable) or --verified-only.' >&2; exit 1 ;;
    esac
done
if [ "$#" -gt 0 ]; then configure=1; fi
options=$(/usr/bin/python3 -I "$root/gpu-vram-sensors.py" --validate-options "$@")
backup="/var/backups/gpu-vram-monitor/$(date +%Y%m%d-%H%M%S)-$$"
install -d -m 700 "$backup"
for file in /usr/local/libexec/gpu-vram-monitor-sensors /etc/systemd/system/gpu-vram-monitor-sensors.service; do
    if [ -e "$file" ]; then cp -a "$file" "$backup/"; fi
done
if [ -d /etc/systemd/system/gpu-vram-monitor-sensors.service.d ]; then
    cp -a /etc/systemd/system/gpu-vram-monitor-sensors.service.d "$backup/"
fi
install -o root -g root -m 755 "$root/gpu-vram-sensors.py" /usr/local/libexec/gpu-vram-monitor-sensors
install -o root -g root -m 644 "$root/gpu-vram-monitor-sensors.service" /etc/systemd/system/gpu-vram-monitor-sensors.service
if [ "$configure" -eq 1 ]; then
    install -d -o root -g root -m 755 /etc/systemd/system/gpu-vram-monitor-sensors.service.d
    override=/etc/systemd/system/gpu-vram-monitor-sensors.service.d/experimental.conf
    printf '[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I /usr/local/libexec/gpu-vram-monitor-sensors %s\n' "$options" > "$override"
    chown root:root "$override"
    chmod 644 "$override"
fi
systemctl daemon-reload
systemctl enable gpu-vram-monitor-sensors.service
systemctl restart gpu-vram-monitor-sensors.service
printf 'Temperature service installed. Backups: %s\n' "$backup"
