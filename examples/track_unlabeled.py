"""
Track unlabeled markers by matching them to known reference positions.

Given a set of reference positions (e.g. (0,0,0) and (0,0,1) in metres),
this script finds whichever unlabeled marker is closest to each reference
position every frame and reports it as that "slot".

Useful when Vicon can see retroreflective markers but they are not assigned
to any subject in Vicon Tracker — e.g. loose markers, ad-hoc setups, or
markers you don't want to configure as a full rigid body.

Usage:
    # Live Vicon — two reference positions in mm
    python examples/track_unlabeled.py --host 192.168.1.10:801 \
        --refs "0,0,0" "0,0,1000"

    # Mock (simulated unlabeled markers, no hardware needed)
    python examples/track_unlabeled.py --mock \
        --refs "0,0,0" "0,0,1000"

Notes:
    - Reference positions are in mm (Vicon world frame).
    - Each frame, the nearest unlabeled marker within --radius mm of each
      reference is reported.  If none is within range, that slot shows NO MATCH.
    - Enable unlabeled marker data in Vicon Tracker:
        Object Tracking → enable "Unlabeled Markers"
"""

import argparse
import time
from typing import List, Optional, Tuple

import numpy as np

from vicon_sdk import MockViconClient, ViconClient
from vicon_sdk.types import Marker, RigidBody


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def find_nearest(
    unlabeled: List[Marker],
    ref_mm: np.ndarray,
    radius_mm: float,
) -> Optional[Marker]:
    """Return the unlabeled marker closest to ref_mm within radius_mm, or None."""
    best: Optional[Marker] = None
    best_dist = float("inf")
    for m in unlabeled:
        if m.occluded:
            continue
        d = float(np.linalg.norm(m.position - ref_mm))
        if d < radius_mm and d < best_dist:
            best_dist = d
            best = m
    return best


# ---------------------------------------------------------------------------
# Mock scene with unlabeled markers
# ---------------------------------------------------------------------------

class MockUnlabeledScene(MockViconClient):
    """
    Generates two unlabeled markers that drift slowly around two reference
    positions.  No subjects — just raw unlabeled markers.
    """

    def __init__(self, refs: List[np.ndarray]):
        super().__init__(subjects={})  # no named subjects
        self._refs = refs

    def _build_frame(self, t):
        frame = super()._build_frame(t)
        # Each marker jiggles ±20 mm around its reference position
        for i, ref in enumerate(self._refs):
            noise = 20.0 * np.array([
                np.sin(t * 0.7 + i),
                np.cos(t * 0.5 + i * 1.3),
                np.sin(t * 0.3 + i * 0.7),
            ])
            frame.unlabeled_markers.append(
                Marker(name=f"unlabeled_{i}", position=ref + noise)
            )
        return frame


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_ref(s: str) -> np.ndarray:
    parts = [float(x.strip()) for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"Reference must be x,y,z — got: {s!r}")
    return np.array(parts)


def main():
    ap = argparse.ArgumentParser(
        description="Track unlabeled Vicon markers by proximity to reference positions"
    )
    ap.add_argument("--host", default="localhost:801")
    ap.add_argument("--mock", action="store_true", help="Use simulated data")
    ap.add_argument(
        "--refs", nargs="+", default=["0,0,0", "0,0,1000"],
        metavar="X,Y,Z",
        help="Reference positions in mm, e.g. --refs '0,0,0' '0,0,1000'",
    )
    ap.add_argument(
        "--radius", type=float, default=200.0,
        help="Max distance in mm to match a marker to a reference (default: 200)",
    )
    ap.add_argument("--rate", type=float, default=5.0, help="Print rate Hz")
    args = ap.parse_args()

    refs: List[np.ndarray] = [parse_ref(r) for r in args.refs]
    labels = [f"ref_{i}  ({r[0]:.0f},{r[1]:.0f},{r[2]:.0f})mm" for i, r in enumerate(refs)]

    if args.mock:
        print("Using mock scene with simulated unlabeled markers.")
        client = MockUnlabeledScene(refs)
    else:
        print(f"Connecting to Vicon at {args.host} …")
        client = ViconClient(args.host)

    print(f"Tracking {len(refs)} reference positions  (radius={args.radius:.0f} mm)\n")

    with client:
        deadline = time.time() + 5.0
        while client.latest_frame is None and time.time() < deadline:
            time.sleep(0.05)
        if client.latest_frame is None:
            raise SystemExit("No frames received.")

        interval = 1.0 / args.rate
        try:
            while True:
                frame = client.latest_frame
                if frame is None:
                    time.sleep(interval)
                    continue

                unlab = frame.unlabeled_markers
                print(f"t={frame.timestamp:.2f}  unlabeled markers in scene: {len(unlab)}")

                for label, ref in zip(labels, refs):
                    match = find_nearest(unlab, ref, args.radius)
                    if match:
                        dx, dy, dz = match.position - ref
                        dist = float(np.linalg.norm(match.position - ref))
                        print(
                            f"  {label:<30}  MATCHED  "
                            f"pos=({match.position[0]:+7.1f},{match.position[1]:+7.1f},{match.position[2]:+7.1f})mm  "
                            f"offset=({dx:+6.1f},{dy:+6.1f},{dz:+6.1f})mm  dist={dist:.1f}mm"
                        )
                    else:
                        print(f"  {label:<30}  NO MATCH within {args.radius:.0f}mm")
                print()
                time.sleep(interval)

        except KeyboardInterrupt:
            print("Stopped.")


if __name__ == "__main__":
    main()
