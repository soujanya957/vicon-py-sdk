# vicon-sdk usage

## Setup

### 1. Get the SDK library

Download from **https://www.vicon.com/software/datastream-sdk/**

The zip extracts to:
```
~/Downloads/ViconDataStreamSDK_1.13.0+167154h/
└── ViconDataStreamSDK_1.13.0+167154h_Mac/
    └── Mac/
        ├── libViconDataStreamSDK_C.dylib   ← needed
        └── ViconDataStreamSDK_CPPTest       ← use to verify connection
```

### 2. Install the library (pick one)

**Auto (SDK in ~/Downloads):**
```bash
bash scripts/install_sdk.sh
```

**Manual path:**
```bash
bash scripts/install_sdk.sh ~/Downloads/ViconDataStreamSDK_.../Mac
```

**Environment variable (no copy):**
```bash
export VICON_SDK_PATH=~/Downloads/ViconDataStreamSDK_.../Mac
```

**Manual copy:**
```bash
cp .../Mac/libViconDataStreamSDK_C.dylib vicon_sdk/
```

Library names by platform: macOS → `.dylib`, Linux → `.so`, Windows → `.dll`

### 3. Verify connection

```bash
# from inside the SDK Mac/ directory
./ViconDataStreamSDK_CPPTest <VICON_IP>
```

If it prints subject names and frame numbers, connection is working.

---

## Connecting

```python
from vicon_sdk import ViconClient
import time

client = ViconClient("192.168.1.10:801")
client.start()

# Wait for first frame (up to 5 s)
deadline = time.time() + 5.0
while client.latest_frame is None and time.time() < deadline:
    time.sleep(0.05)

client.stop()
```

**Context manager (recommended):**
```python
with ViconClient("192.168.1.10:801") as client:
    time.sleep(0.3)
    frame = client.latest_frame
```

**Without hardware:**
```python
from vicon_sdk import MockViconClient
import numpy as np

with MockViconClient(subjects={"robot": np.array([500, 0, 400])}) as client:
    time.sleep(0.1)
    frame = client.latest_frame
```

---

## Reading a frame

```python
frame = client.latest_frame   # ViconFrame | None

frame.timestamp               # Unix time (float)
frame.subject_names()         # ['robot', 'camera', ...]
frame.subjects                # dict[str, RigidBody]
frame.markers                 # dict["subject/marker", Marker]
frame.unlabeled_markers       # list[Marker] — markers not assigned to any subject
```

---

## Subjects (rigid bodies)

```python
body = frame.subject("my_robot")   # RigidBody | None

body.name                  # "my_robot"
body.position              # np.ndarray [x, y, z] mm
body.rotation_quat         # np.ndarray [qx, qy, qz, qw]
body.rotation_matrix       # np.ndarray 3×3
body.occluded              # bool — True if pose could not be solved
body.quality               # float 0.0–1.0 | None — tracking quality
body.markers               # list[Marker] — individual markers on this subject
body.marker_by_name("tip") # Marker | None
```

---

## Individual markers

```python
# Labeled marker (part of a subject)
m = frame.marker("robot", "tip_marker")   # Marker | None
m.position    # np.ndarray [x, y, z] mm
m.occluded    # bool

# Unlabeled markers (not assigned to any subject)
for m in frame.unlabeled_markers:
    print(m.position)
```

---

## Canvas / planar surface (4-marker target)

```python
from vicon_sdk import CanvasFrame, sort_corners

# Get four corner markers (order doesn't matter — sort_corners handles it)
pts = [frame.marker("canvas", f"c{i}").position for i in range(1, 5)]
canvas = CanvasFrame(sort_corners(pts))

canvas.width_mm, canvas.height_mm  # physical size
canvas.x_axis, canvas.y_axis       # unit vectors (TL→TR, TL→BL)
canvas.normal                       # unit normal away from surface
canvas.center                       # centre position mm

# Convert world point → UV (0,0=TL  1,1=BR)
u, v = canvas.world_to_uv(some_point_mm)

# Convert UV → world (optionally lifted above surface)
pt = canvas.uv_to_world(0.5, 0.5, z_offset_mm=10.0)

# Signed distance from a point to the canvas plane
dist = canvas.distance_to_mm(some_point_mm)

canvas.is_valid()   # True if 4 corners with non-zero dimensions
```

---

## Unlabeled markers — proximity tracking

Match unlabeled markers to known reference positions:

```python
import numpy as np

ref_a = np.array([0.0, 0.0, 0.0])      # mm
ref_b = np.array([0.0, 0.0, 1000.0])   # mm
radius = 200.0  # mm

for m in frame.unlabeled_markers:
    dist_a = np.linalg.norm(m.position - ref_a)
    dist_b = np.linalg.norm(m.position - ref_b)
    if dist_a < radius:
        print("Marker near ref_a:", m.position)
    elif dist_b < radius:
        print("Marker near ref_b:", m.position)
```

See `examples/track_unlabeled.py` for a full working example.

---

## Frame rate & quality

```python
# Frame rate is read directly from the SDK (live client only)
# Access via the low-level SDK client if needed:
from vicon_sdk.sdk import ViconSDKClient
with ViconSDKClient() as c:
    c.connect("192.168.1.10:801")
    c.enable_segment_data()
    c.set_stream_mode()
    c.get_frame()
    print(c.get_frame_rate())          # Hz
    print(c.get_object_quality("robot"))  # 0.0–1.0

# Via the high-level client, quality is included on every RigidBody:
body = frame.subject("robot")
if body and body.quality is not None:
    if body.quality < 0.3:
        print("Poor tracking quality — check marker visibility")
```

---

## Local frame pose (hierarchical rigs)

For multi-segment subjects, get pose relative to the parent segment:

```python
from vicon_sdk.sdk import ViconSDKClient

with ViconSDKClient() as c:
    c.connect("192.168.1.10:801")
    c.enable_segment_data()
    c.set_stream_mode()
    c.get_frame()
    trans, occ = c.get_segment_local_translation("Alice", "RightArm")
    rot,   _   = c.get_segment_local_rotation_quaternion("Alice", "RightArm")
```

---

## ViconSDKClient — low-level access

For anything not exposed by the high-level `ViconClient`, use `ViconSDKClient` directly:

```python
from vicon_sdk.sdk import ViconSDKClient, CLIENT_PULL, SUCCESS

with ViconSDKClient() as c:
    c.connect("192.168.1.10:801")
    c.enable_segment_data()
    c.enable_marker_data()
    c.enable_unlabeled_marker_data()
    c.set_stream_mode(CLIENT_PULL)

    while True:
        if c.get_frame() == SUCCESS:
            n = c.get_subject_count()
            for i in range(n):
                name = c.get_subject_name(i)
                trans, occ = c.get_segment_global_translation(name, name)
                print(name, trans)
```

**Full method list:**

| Method | Returns |
|--------|---------|
| `connect(host)` | result code |
| `disconnect()` | — |
| `is_connected()` | bool |
| `enable_segment_data()` | — |
| `enable_marker_data()` | — |
| `enable_unlabeled_marker_data()` | — |
| `set_stream_mode(mode)` | — |
| `get_frame()` | result code |
| `wait_for_frame()` | result code (blocks) |
| `get_frame_number()` | int \| None |
| `get_frame_rate()` | float \| None (Hz) |
| `get_subject_count()` | int |
| `get_subject_name(i)` | str \| None |
| `get_subject_root_segment_name(subject)` | str \| None |
| `get_segment_count(subject)` | int |
| `get_segment_name(subject, i)` | str \| None |
| `get_segment_global_translation(subject, segment)` | ([x,y,z], occluded) |
| `get_segment_global_rotation_quaternion(subject, segment)` | ([qx,qy,qz,qw], occluded) |
| `get_segment_local_translation(subject, segment)` | ([x,y,z], occluded) |
| `get_segment_local_rotation_quaternion(subject, segment)` | ([qx,qy,qz,qw], occluded) |
| `get_marker_count(subject)` | int |
| `get_marker_name(subject, i)` | str \| None |
| `get_marker_global_translation(subject, marker)` | ([x,y,z], occluded) |
| `get_unlabeled_marker_count()` | int |
| `get_unlabeled_marker_global_translation(i)` | ([x,y,z], occluded) |
| `get_object_quality(subject)` | float \| None (0–1) |
