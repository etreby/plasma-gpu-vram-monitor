# Included RTX 3090 sensor reader

The widget no longer calls gputemps. A small Python standard-library service
reads RTX 3090 hotspot and VRAM thermal registers and publishes an atomic JSON
cache. It has no libpci, NVML Python binding, third-party Python package, kernel
module, or /dev/mem dependency. nvidia-smi provides the other GPU metrics.

## Access and support

The service identifies NVIDIA display devices using sysfs vendor/device/class
IDs and checks that the nvidia driver is bound and the device is active. Its
initial allowlist is **10de:2204 only**. It maps one BAR0 page at a time from the
device's sysfs `resource0`, opened read-only with `PROT_READ`. There is no code
path that writes GPU registers or accepts arbitrary offsets from the widget.
No runtime-suspended device is intentionally awakened.

The system service runs an isolated Python interpreter from a root-owned file,
has CAP_SYS_RAWIO as its only bounded capability, read-only system files,
protected home directories, and a private root-owned runtime directory. Only
the JSON readings are public. There is no user-editable privileged configuration
or sudoers grant. Administrators explicitly install it using sensors/install.sh;
the normal widget installer does not request elevated privileges.

Kernel lockdown, resource mapping restrictions and other hardware may prevent
access. A device disappearing during an MMIO read may terminate the reader;
systemd restarts it and the widget rejects stale cached readings after 15 seconds.
The service has not been reboot-tested. Only the two local RTX 3090 cards have
been validated. This does not claim support for all GDDR6/GDDR6X/GDDR7 GPUs.

## Register facts and provenance

This is a newly authored implementation, not a clean-room reverse-engineering
claim. The existing gputemps source was inspected before implementation. The
following hardware facts were learned from that project:

| RTX 3090 BAR0 offset | Interpretation |
| --- | --- |
| `0xE2A8` | VRAM temperature is the low 12 bits, divided by 32, in Celsius |
| `0x2046C` | Hotspot temperature is bits 8–15, in Celsius |

No upstream source files, library objects, or executable are included or invoked.
The new reader uses a different access mechanism (sysfs PCI resources instead
of the upstream libpci + physical-memory approach), a different output interface
(PCI-keyed atomic cache), and a deliberately narrow hardware allowlist.
Attribution to the published register research is retained here. The project
and newly authored reader remain GPL-3.0; this change does not remove licensing
from our code or claim independent discovery of NVIDIA's register layout.

References:

- [Linux PCI sysfs resource interface](https://docs.kernel.org/PCI/sysfs-pci.html)
- [NVIDIA nvidia-smi temperature documentation](https://docs.nvidia.com/deploy/nvidia-smi/index.html)
- [Register research / gputemps source inspected](https://github.com/ThomasBaruzier/gddr6-core-junction-vram-temps/tree/6d8c5ecf633a8658d205fb2c24531bf87164912f)

## Validation

New-reader and upstream-reader one-shot samples agreed on VRAM and hotspot
readings for both cards. Tests cover cache expiration and malformed data,
PCI matching with reordered NVIDIA output, unsupported/suspended devices,
permission failures, invalid register values, atomic publication, and missing
sensor-service behavior. Live service-stop/restart checks verify that usage
continues without temperature data and readings recover when the service returns.
