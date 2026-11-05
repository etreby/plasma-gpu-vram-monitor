# Per-GPU process activity

Click a GPU's panel section to open the activity view for that device. The
selector also includes GPUs with process statistics but no aggregate sensors
(such as the local Intel integrated GPU). These process-only cards do not expand
the compact panel. Search by name/PID, sort by memory/GPU activity/name, and click
a row for its memory scope and any sharing caveat. Pause freezes the task list
while device summary sampling continues; resume or refresh for a new snapshot.

## What the numbers mean

| Source | Processes | GPU memory | GPU % |
| --- | --- | --- | --- |
| NVIDIA driver XML + pmon | Graphics and compute contexts reported by the driver | Driver-reported allocation; tagged XML units preferred over pmon fallback | SM active time from pmon where supported |
| Linux DRM fdinfo | GPU clients readable by the current user | Resident local/VRAM buffers preferred; otherwise requested local buffers or GPU buffers in system RAM, explicitly labeled | Busiest engine from two busy-time snapshots, normalized by engine capacity |

GPU % is an activity measurement, not a division of the total GPU load among
processes. Independent engines can operate concurrently. Memory activity % is
also not memory allocation. An app can reserve memory while doing no GPU work.
A dash means unavailable, not 0. The driver can reserve device memory that is not
attributable to any listed task. Shared buffers can overlap between clients, so
summing process rows is not a reliable device-total calculation.

NVIDIA's process list includes graphics and compute tasks, unlike a compute-only
query. pmon is invoked in groups of at most four GPUs for compatibility with
older driver versions; group requests are parallel. Per-device mapping retains
the driver's original enumeration index and the physical PCI address even when
the widget's display order differs. Unsupported utilization (including many
GeForce graphics contexts and some MIG configurations) stays unavailable.
Duplicate XML contexts for a PID use the largest reported allocation rather
than adding potentially overlapping contexts; a row note explains that limit.

DRM snapshots deduplicate repeated descriptors by device and drm-client-id.
Each process is identified with its PID and start time to avoid PID-reuse errors.
Engine counter resets or missing first samples do not become activity spikes.
Engine group capacity is honored. Multiple unique clients for one PID sum their
reported allocations and engine activity, with a shared-buffer caveat. Shared
client counters across PIDs are attributed once; other visible owners receive
rows pointing to the primary PID, without duplicating its counters. Requested
buffer sizes and resident allocations are distinguished in the row tooltip.
A process with client allocations in different memory scopes is explicitly
labeled as mixed GPU buffers, not solely dedicated VRAM.

The process list can be incomplete because of driver support, Linux procfs
permissions, containers, disappearing processes or shared/MIG contexts. DRM
visibility is always described as limited. An empty DRM list means no visible
clients, not proof that the device is idle. A failed NVIDIA process query is
reported as unavailable rather than an idle GPU. One backend failing does not
hide the other vendor's task data.

## Sampling, permissions and privacy

Task collection runs only when the expanded view requests `--processes`.
`--task-inventory` retains process-only GPU choices while tasks are paused, but
does not inspect processes. The closed panel keeps its original light telemetry.
In-flight requests can finish after the popup closes; their task snapshot is not
retained in the view. Process information is held in memory, not written to a
cache, and all collection runs as the normal desktop user. No sudo, accounting
mode changes, process control or GPU setting changes are involved.

The UI exposes process names (basenames), PIDs, type, memory and activity. It
does not read command-line arguments or environment variables. Diagnostic mode
always excludes process data, including if `--processes` is also supplied. No
reports or process data are uploaded automatically. Review screenshots before
sharing them: they can identify which applications you have running.

For a local terminal snapshot:

```sh
~/.local/bin/gpu-panel-data --processes
```

## Validation scope

Live validation: two RTX 3090 devices for NVIDIA process-list/empty states, and
Intel `8086:7d67` using i915 for per-process system-memory GPU buffers and engine
activity. The NVIDIA driver returned allocation but no SM-utilization numbers
for the graphics tasks observed here. Synthetic tests cover pmon schema changes,
multiple GPUs, missing values, memory units, DRM engine capacity, counter resets,
PID reuse, duplicate/shared clients and privacy. AMD/Nouveau/platform process
paths are not claimed as hardware-verified by those fixtures.

Native QML checks covered selection, populated and empty lists, PID/name
filtering, clearing filters, sorting, and task pause/resume. Screenshots show
real local data; fixtures used in tests are explicitly synthetic.

References:

- [NVIDIA process monitoring](https://docs.nvidia.com/deploy/nvidia-smi/index.html#process-monitoring)
- [Linux DRM client statistics](https://docs.kernel.org/gpu/drm-usage-stats.html)
