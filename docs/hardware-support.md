# Hardware support and community validation

There are two independent paths: normal driver telemetry and opt-in low-level
NVIDIA thermal profiles. Neither requires owning every supported GPU to develop,
but simulated tests do not establish real-card compatibility.

## Current matrix

| Hardware / path | Tier | Default | Coverage |
| --- | --- | --- | --- |
| NVIDIA RTX 3090 `10de:2204` direct thermals | Verified on two local boards | Enabled | VRAM and hotspot; EVGA/ZOTAC test coverage, not every board/driver combination |
| RTX 3080 `10de:2206`, `220a`, `2216` | Experimental, researched candidate | Disabled | Same researched thermal layout; no real-card validation here |
| RTX 3080 Ti `10de:2208` | Experimental, researched candidate | Disabled | Same researched thermal layout; no real-card validation here |
| RTX 3090 Ti `10de:2203` | Experimental, researched candidate | Disabled | Same researched thermal layout; no real-card validation here |
| Other NVIDIA cards via nvidia-smi | Driver-provided | Enabled | Core/load/VRAM allocation; memory temperature only if driver exposes it |
| AMD using amdgpu sysfs/hwmon | Driver-provided, synthetic tests only | Enabled when readable | Labeled core/junction/memory temperatures; GPU/memory busy % and VRAM allocation where exposed |
| Intel using i915/xe hwmon | Driver-provided, synthetic tests only | Enabled when readable | GPU-specific temperature channels only where exposed; no invented load or dedicated VRAM |
| Legacy AMD radeon / NVIDIA nouveau | Driver-provided, synthetic tests only | Enabled when readable | GPU core temperature from documented GPU-attached hwmon |
| Other PCI/DRM GPUs, including platform devices | Detected; telemetry conditional | Discovery enabled | Read explicitly GPU-labeled hwmon from the bound driver; otherwise report missing sensors |
| Unknown NVIDIA direct-register layout | Unsupported | Blocked | No fallback to another architecture's registers |

All GPU sensor files are optional. A discovered GPU without usable readings is omitted from the compact panel
metrics but remains in the details view and diagnostic inventory with a status.
The documented Intel GPU-package sensor is accepted only from GPU-attached
i915/xe hwmon; CPU coretemp/package sensors are not used. NVIDIA
failure does not prevent AMD/Intel sensors from working. Names for non-NVIDIA GPUs
currently use the vendor and PCI device ID, without adding a pci.ids dependency.

The popup/tooltip and diagnostic JSON distinguish `verified`, `experimental`,
`driver-provided` and `unavailable`. Sources are reported per temperature channel;
a driver-provided VRAM reading may coexist with an experimental hotspot reading.
`legacy-cache` means the optional service is an older release and should be
upgraded. A driver-provided source does not mean we tested that model ourselves.

## Process telemetry

v1.5 adds NVIDIA graphics/compute tasks and unprivileged Linux DRM process
statistics where exposed. Live i915 process activity and GPU buffers were
verified on local Intel `8086:7d67`, despite its lack of aggregate sensors.
Other Intel/AMD/Nouveau/platform process support remains conditional on driver
fdinfo support and procfs permissions. Per-process VRAM/usage are not guaranteed
on every card. [Process measurement details](process-monitoring.md).

## Broad coverage boundaries

PCI display-class devices and DRM card/device links are discovered independently
of model and vendor whitelists. Multiple DRM nodes for one physical device are
deduplicated. DRM-only platform GPUs use a platform identity instead of a made-up
PCI address. Virtual GPUs are discoverable if represented by these interfaces;
they frequently have no physical thermal sensors.

The generic hwmon path only accepts a hwmon device associated with the GPU and
named for its bound driver (nouveau also allows nvkm). Known drivers' documented
unlabeled temp1 sensors are treated as core/GPU-package temperature. Other
backends require explicit GPU/core/memory/hotspot labels; arbitrary temperature
channels, CPU packages and nearby thermal zones are not guessed.

NVIDIA's optional memory-temperature CSV field can be rejected by older drivers.
The helper then tries nvidia-smi XML and reads only the supported numeric fields.
Malformed or missing fields stay unavailable. A synthetic GTX 1080 fixture tests
this behavior; it is not a claim that a physical GTX 1080 was tested.

Every live card reports capability booleans and missing-metric reasons in JSON.
A driver with no exposed metrics is reported as no-readable-sensors, suspended,
or no-driver. Discovering a GPU is not the same as providing its VRAM temperature.
The project cannot promise every metric on every card: some sensors or supported
interfaces do not exist. Direct-register access remains separately allowlisted.
No NVIDIA 10/20/40/50-series direct thermal support is introduced by broad discovery.

## Explicit experimental opt-in

Check the PCI device ID in the unprivileged report, then use the complete source
bundle. For an RTX 3080 with ID 2206:

```sh
sudo ./sensors/install.sh --experimental-device 2206
```

Repeat the argument for multiple researched IDs. Unknown IDs are rejected before
installation. No widget setting can enable register access or change offsets.
There is no wildcard "try every GPU" option. The register offsets are fixed in
the root-owned reader. Each enabled device must still pass driver, active power
state and BAR resource checks.

To return to verified-only profiles:

```sh
sudo ./sensors/install.sh --verified-only
```

Opt-in settings live in the root-owned systemd drop-in
`/etc/systemd/system/gpu-vram-monitor-sensors.service.d/experimental.conf`.
Installing without arguments preserves a prior opt-in. Installer backups include
this directory. For a one-shot, explicit register test on researched hardware:

```sh
sudo /usr/local/libexec/gpu-vram-monitor-sensors --once --experimental-device 2206
```

This is experimental access to undocumented hardware registers. Plausible numbers
are not proof of correctness. We have not tested these profiles under load, on
hybrid laptops, across suspend/resume, or with other drivers/firmware. Unsupported
cards, and all 40/50-series direct-register profiles, stay blocked in this release.

## Submit a local report

Run as your normal user:

```sh
~/.local/bin/gpu-panel-data --diagnose > gpu-report.json
```

The command generates JSON locally and does not access raw registers, invoke
sudo or upload anything. It includes the widget/kernel/NVIDIA driver versions,
PCI vendor/device/subsystem IDs, driver names, power states and current readings
with sources. It deliberately excludes hostnames, usernames, GPU UUIDs, serial
numbers, process lists and environment variables. Review it before posting.

Open a [GPU compatibility report](https://github.com/etreby/plasma-gpu-vram-monitor/issues/new?template=hardware-test.yml).
Include board model, PCI ID, driver/kernel/Plasma versions, diagnostic output,
and idle/load comparisons with a named reference tool and version. Crop unrelated
desktop content out of screenshots. Explain timing and OS differences; values
measured after reboot or under a different load are not simultaneous comparisons.

## Promotion to verified

Promotion is a manual source change with evidence linked in this file:

1. A real tester confirms the exact PCI/subsystem IDs and software environment.
2. Independent reference readings support the channel interpretation at idle and
   under load, with no unexplained flat, zero, impossible or swapped values.
3. Repeated samples, service stop/start, sensor-unavailable behavior and
   suspend/resume are checked on the actual board.
4. Record the tested board/driver scope and remaining gaps; add a sanitized real
   fixture with provenance and permission to publish it. Keep synthetic fixtures
   labeled synthetic. A second independent board/tester is preferred before
   generalizing a result to the model family.

A JSON report alone, plausibility checks or passing fixture tests never
promote a profile automatically. No community confirmations are claimed yet.

## Research references

- [NVIDIA PCI device-ID table](https://download.nvidia.com/XFree86/Linux-x86_64/570.124.04/README/supportedchips.html)
- [Published pre-Blackwell thermal layout research](https://github.com/ThomasBaruzier/gddr6-core-junction-vram-temps/blob/6d8c5ecf633a8658d205fb2c24531bf87164912f/src/sensor.c)
- [Linux amdgpu thermal and busy-percent ABI](https://docs.kernel.org/gpu/amdgpu/thermal.html)
- [Linux amdgpu memory accounting ABI](https://docs.kernel.org/gpu/amdgpu/driver-misc.html)
- [Intel i915 GPU-package temperature ABI](https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-driver-intel-i915-hwmon)
- [Nouveau thermal interface](https://docs.kernel.org/driver-api/thermal/nouveau_thermal.html)
- [Linux hwmon labels, units and optional attributes](https://docs.kernel.org/hwmon/sysfs-interface.html)

PCI IDs identify products; NVIDIA's ID list does not document or validate our
thermal registers. The experimental GA102 layout is an inference from published
register research and architecture, pending real-card tests. Intel coverage is
only an opportunistic reader of standard GPU hwmon attributes; no Intel VRAM
thermal support is claimed without such a driver attribute.
