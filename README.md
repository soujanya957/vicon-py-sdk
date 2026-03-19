# vicon-sdk

A lightweight, thread-safe Python client for streaming motion-capture data from a [Vicon](https://www.vicon.com) system using the official Vicon DataStream C SDK.

**No pip-installed Vicon package needed** — just the compiled C shared library (`.dylib` / `.so` / `.dll`) from the official SDK download, and this library wraps it via `ctypes`.

---

## Features

- Stream all tracked rigid bodies and markers from a live Vicon system
- Background thread — call `client.latest_frame` from anywhere, any time
- `MockViconClient` for development and testing without hardware
- `CanvasFrame` utility for tracking flat planar surfaces with four corner markers
- Works on macOS, Linux, and Windows
- Pure Python — only dependency is `numpy`

---

## Connecting to Vicon

Vicon communicates over **Ethernet** (not Wi-Fi). Connect your machine directly to the Vicon switch or router with an Ethernet cable. The default DataStream port is `801`.

**Verify you're receiving data** before using this library by running the test binary that ships with the SDK:

```bash
# macOS / Linux — from inside the SDK Mac/ or Linux64/ directory
./ViconDataStreamSDK_CPPTest <VICON_HOST_IP>
```

If it prints subject names and frame numbers, your connection is working and you're ready to use `ViconClient("<VICON_HOST_IP>:801")`.

If it hangs or errors, check:
- Ethernet is physically connected and the interface has an IP on the same subnet as Vicon
- The Vicon Tracker / Nexus software is running on the Vicon PC
- No firewall is blocking port 801

---

## Requirements

- Python 3.8+
- `numpy >= 1.21`
- The Vicon DataStream C SDK shared library (see below)

---

## Installation

```bash
pip install vicon-sdk
```

Or install directly from this repo:

```bash
git clone https://github.com/YOUR_USERNAME/vicon-py-sdk.git
cd vicon-py-sdk
pip install -e .
```

---

## Getting the Vicon SDK library

Download the **Vicon DataStream SDK** from:
**https://www.vicon.com/software/datastream-sdk/**

The zip extracts to a folder structure like this:

```
~/Downloads/
└── ViconDataStreamSDK_1.13.0+167154h/
    └── ViconDataStreamSDK_1.13.0+167154h_Mac/
        └── Mac/
            ├── libViconDataStreamSDK_C.dylib   ← this is the file we need
            ├── libViconDataStreamSDK_CPP.dylib
            └── ViconDataStreamSDK_CPPTest       ← useful for testing connectivity
```

### Option 1 — install script (recommended)

If the SDK was downloaded to `~/Downloads` (the default save location), the install script finds it automatically:

```bash
bash scripts/install_sdk.sh
```

It searches `~/Downloads/ViconDataStreamSDK_*` for the library and copies it into the package so that `import vicon_sdk` works with no extra config.

If the SDK is saved somewhere else, pass the platform directory path explicitly:

```bash
# macOS
bash scripts/install_sdk.sh ~/Downloads/ViconDataStreamSDK_1.13.0+167154h/ViconDataStreamSDK_1.13.0+167154h_Mac/Mac

# Linux
bash scripts/install_sdk.sh ~/Downloads/ViconDataStreamSDK_1.13.0+167154h/ViconDataStreamSDK_1.13.0+167154h_Linux/Linux64
```

### Option 2 — environment variable

If you don't want to copy the file, set `VICON_SDK_PATH` to the platform directory and the library will be found at runtime automatically:

```bash
export VICON_SDK_PATH=~/Downloads/ViconDataStreamSDK_1.13.0+167154h/ViconDataStreamSDK_1.13.0+167154h_Mac/Mac
```

Add this to `~/.zshrc` or `~/.bashrc` to make it permanent.

### Option 3 — manual copy

Copy the library file directly next to `vicon_sdk/sdk.py`:

```bash
# macOS
cp ~/Downloads/ViconDataStreamSDK_1.13.0+167154h/ViconDataStreamSDK_1.13.0+167154h_Mac/Mac/libViconDataStreamSDK_C.dylib vicon_sdk/

# Linux
cp ~/Downloads/ViconDataStreamSDK_1.13.0+167154h/ViconDataStreamSDK_1.13.0+167154h_Linux/Linux64/libViconDataStreamSDK_C.so vicon_sdk/
```

The library file for each platform:

| Platform | Directory | Library file |
|----------|-----------|-------------|
| macOS    | `Mac/`    | `libViconDataStreamSDK_C.dylib` |
| Linux    | `Linux64/`| `libViconDataStreamSDK_C.so` |
| Windows  | `Win64/`  | `ViconDataStreamSDK_C.dll` |

> **Note:** The library is not included in this repo (it's Vicon's proprietary binary).
> `MockViconClient` works without it — no download needed for testing.

---

## Quick start

### Live Vicon system

```python
import time
from vicon_sdk import ViconClient

client = ViconClient("192.168.1.10:801")
client.start()

# Wait for the first frame
deadline = time.time() + 5.0
while client.latest_frame is None and time.time() < deadline:
    time.sleep(0.05)

frame = client.latest_frame
body  = frame.subject("my_robot")

if body and not body.occluded:
    print("Position (mm):", body.position)
    print("Quaternion [qx,qy,qz,qw]:", body.rotation_quat)

client.stop()
```

### Context manager (auto start/stop)

```python
from vicon_sdk import ViconClient
import time

with ViconClient("192.168.1.10:801") as client:
    time.sleep(0.5)
    frame = client.latest_frame
    print(frame.subject_names())
```

### Without hardware — MockViconClient

```python
import numpy as np
import time
from vicon_sdk import MockViconClient

with MockViconClient(subjects={"robot": np.array([500, 0, 400])}) as client:
    time.sleep(0.1)
    frame = client.latest_frame
    body  = frame.subject("robot")
    print(body.position)
```

---

## Tracking a planar canvas (4-marker surface)

If you have a flat surface tracked with four retroreflective markers, use `CanvasFrame` and `sort_corners` to get the local coordinate frame and UV conversions:

```python
import numpy as np
from vicon_sdk import CanvasFrame, sort_corners

# Four marker positions from a Vicon frame (order doesn't matter)
raw_corners = [
    frame.marker("canvas", "canvas1").position,
    frame.marker("canvas", "canvas2").position,
    frame.marker("canvas", "canvas3").position,
    frame.marker("canvas", "canvas4").position,
]

canvas = CanvasFrame(sort_corners(raw_corners))

print(f"Size: {canvas.width_mm:.0f} mm × {canvas.height_mm:.0f} mm")
print("x_axis:", canvas.x_axis)
print("y_axis:", canvas.y_axis)
print("normal:", canvas.normal)

# Project a world-frame point onto the canvas
u, v = canvas.world_to_uv(some_point_mm)
print(f"UV: ({u:.3f}, {v:.3f})")   # 0,0 = TL corner; 1,1 = BR corner

# Get world-frame position at canvas centre, 10 mm above the surface
centre = canvas.uv_to_world(0.5, 0.5, z_offset_mm=10.0)
```

---

## API reference

### `ViconClient(host="localhost:801")`

Streams live data from a Vicon DataStream server.

| Method | Description |
|--------|-------------|
| `start()` | Start background streaming thread |
| `stop()` | Stop thread and disconnect |
| `latest_frame` | Most recent `ViconFrame`, or `None` |

### `MockViconClient(rate_hz=100, subjects=None)`

Simulates subjects with a slow circular orbit. Pass `subjects={"name": np.array([x,y,z])}` to configure. Subclass and override `_build_frame(t)` for custom motion.

### `ViconFrame`

| Attribute / Method | Description |
|-------------------|-------------|
| `timestamp` | Unix time of capture |
| `subjects` | `dict[str, RigidBody]` — all tracked subjects |
| `markers` | `dict[str, Marker]` — all markers, keyed `"subject/marker"` |
| `subject(name)` | Returns `RigidBody` or `None` |
| `marker(subject, marker)` | Returns `Marker` or `None` |
| `subject_names()` | List of all subject names |

### `RigidBody`

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Subject name |
| `position` | `np.ndarray (3,)` | [x, y, z] in mm |
| `rotation_quat` | `np.ndarray (4,)` | [qx, qy, qz, qw] |
| `rotation_matrix` | `np.ndarray (3,3)` | Derived from quaternion |
| `markers` | `list[Marker]` | Individual markers |
| `occluded` | `bool` | True if pose was unsolvable |
| `marker_by_name(name)` | | Lookup marker by name |

### `CanvasFrame(corners)`

| Property / Method | Description |
|------------------|-------------|
| `origin` | TL corner position (mm) |
| `x_axis` | Unit vector TL→TR |
| `y_axis` | Unit vector TL→BL |
| `normal` | Unit normal away from surface |
| `center` | Canvas centre (mm) |
| `width_mm`, `height_mm` | Physical dimensions |
| `is_valid()` | True if 4 corners with non-zero size |
| `world_to_uv(point_mm)` | Project world point → (u, v) |
| `uv_to_world(u, v, z_offset_mm=0)` | UV → world-frame position |
| `distance_to_mm(point_mm)` | Signed distance to canvas plane |

### `sort_corners(pts)`

Sort four unsorted corner marker positions into [TL, TR, BR, BL] order. Assumes the canvas is roughly in the XY plane.

---

## Examples

### Zero-setup quickstart (no hardware, no SDK download needed)

```bash
python examples/quickstart.py
```

Demonstrates the full API — streaming, subject lookup, canvas tracking, UV
coordinate conversion — using `MockViconClient`.

### Print all subjects

```bash
python examples/print_subjects.py --mock                     # simulated
python examples/print_subjects.py --host 192.168.1.10:801   # live
```

### Track a four-marker canvas plane

```bash
python examples/canvas_tracker.py --mock
python examples/canvas_tracker.py --host 192.168.1.10:801
```

### Record subjects to CSV

```bash
python examples/record_csv.py --mock --duration 10 --out recording.csv
python examples/record_csv.py --host 192.168.1.10:801 --out recording.csv
```

Output format: `timestamp, subject, x_mm, y_mm, z_mm, qx, qy, qz, qw, occluded`

---

## Vicon subject naming

The client discovers **all subjects** currently tracked in the Vicon scene automatically — no configuration needed. Name your subjects in Vicon Tracker or Nexus, then access them by name:

```python
body = frame.subject("my_robot_name")
```

---

## License

MIT
