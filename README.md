# vicon-sdk

Lightweight Python client for the [Vicon DataStream SDK](https://www.vicon.com/software/datastream-sdk/).
Wraps the official C shared library via `ctypes` — no pip-installed Vicon bindings needed.

```python
from vicon_sdk import ViconClient

with ViconClient("192.168.1.10:801") as client:
    frame = client.latest_frame
    body  = frame.subject("my_robot")
    print(body.position)   # [x, y, z] in mm
```

**No hardware?** `MockViconClient` works with zero setup — see `examples/quickstart.py`.

---

## Install

```bash
git clone https://github.com/YOUR_USERNAME/vicon-py-sdk.git
cd vicon-py-sdk
pip install -e .
```

Then install the SDK library (see [USAGE.md](USAGE.md)):

```bash
bash scripts/install_sdk.sh
```

> **macOS:** The script copies all `.dylib` files from the SDK folder.
> `libViconDataStreamSDK_C.dylib` depends on `libViconDataStreamSDK_CPP.dylib` —
> both must be present in `vicon_sdk/` or the library will fail to load.
>
> If you see `Library not loaded: libViconDataStreamSDK_CPP.dylib`, copy all
> `.dylib` files manually:
> ```bash
> cp /path/to/Mac/*.dylib vicon_sdk/
> ```
>
> Also ensure your macOS version is not older than what the SDK was compiled for
> (`built for macOS X.X` in the error means your OS is too old).

---

## Connection

Vicon communicates over **Ethernet only** (not Wi-Fi). Connect directly to the Vicon switch with an Ethernet cable.

Verify your connection with the test binary that ships with the SDK:

```bash
# from inside the SDK Mac/ or Linux64/ directory
./ViconDataStreamSDK_CPPTest <VICON_IP>
```

If it prints frame numbers and subject names, you're ready.

---

## Examples

| Script | What it shows |
|--------|--------------|
| `examples/quickstart.py` | Full API with no hardware — run this first |
| `examples/print_subjects.py` | Stream and print all tracked subjects |
| `examples/canvas_tracker.py` | 4-marker planar surface + UV coordinates |
| `examples/record_csv.py` | Record subjects to CSV |
| `examples/track_unlabeled.py` | Match unlabeled markers to reference positions |

---

## What's covered from the SDK

| Category | Functions |
|----------|-----------|
| Connection | `connect`, `disconnect`, `is_connected` |
| Frames | `get_frame`, `wait_for_frame`, `get_frame_number`, `get_frame_rate` |
| Subjects | `get_subject_count/name`, `get_segment_count/name` |
| Global pose | `get_segment_global_translation/rotation_quaternion` |
| Local pose | `get_segment_local_translation/rotation_quaternion` |
| Markers | `get_marker_count/name/global_translation` |
| Unlabeled markers | `get_unlabeled_marker_count/global_translation` |
| Quality | `get_object_quality` (0.0–1.0 per subject) |

See [USAGE.md](USAGE.md) for full API reference.

---

## License

MIT
