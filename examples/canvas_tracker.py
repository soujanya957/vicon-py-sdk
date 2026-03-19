"""
Track a four-marker canvas and print its geometry every second.

Expects a Vicon subject called "canvas" with four markers named
canvas1, canvas2, canvas3, canvas4.  The markers are automatically
sorted into TL / TR / BR / BL order.

Usage:
    python examples/canvas_tracker.py --host 192.168.1.10:801
    python examples/canvas_tracker.py --mock
"""

import argparse
import time

import numpy as np

from vicon_sdk import CanvasFrame, MockViconClient, ViconClient, sort_corners
from vicon_sdk.types import RigidBody, Marker

CANVAS_SUBJECT = "canvas"
CANVAS_MARKERS = ["canvas1", "canvas2", "canvas3", "canvas4"]

SEP = "─" * 60


def get_canvas_from_frame(frame, subject=CANVAS_SUBJECT, marker_names=CANVAS_MARKERS):
    """Extract and sort four canvas markers into a CanvasFrame."""
    pts = []
    for mname in marker_names:
        m = frame.marker(subject, mname)
        if m is None or m.occluded:
            return None
        pts.append(m.position.copy())
    if len(pts) != 4:
        return None
    return CanvasFrame(sort_corners(pts))


def main():
    ap = argparse.ArgumentParser(description="Track a 4-marker canvas plane")
    ap.add_argument("--host", default="localhost:801",
                    help="Vicon DataStream server address")
    ap.add_argument("--mock", action="store_true",
                    help="Use simulated canvas data")
    ap.add_argument("--subject", default=CANVAS_SUBJECT,
                    help=f"Subject name (default: {CANVAS_SUBJECT})")
    ap.add_argument("--markers", nargs=4,
                    default=CANVAS_MARKERS,
                    metavar="M",
                    help="Four marker names (default: canvas1 canvas2 canvas3 canvas4)")
    args = ap.parse_args()

    if args.mock:
        print("Using mock Vicon client.")
        client = _MockCanvasClient()
    else:
        print(f"Connecting to Vicon at {args.host} …")
        client = ViconClient(args.host)

    with client:
        deadline = time.time() + 5.0
        while client.latest_frame is None and time.time() < deadline:
            time.sleep(0.05)
        if client.latest_frame is None:
            raise SystemExit("No frames received.")

        print("Connected.\n")

        try:
            while True:
                frame = client.latest_frame
                if frame is None:
                    time.sleep(1.0)
                    continue

                canvas = get_canvas_from_frame(frame, args.subject, args.markers)

                print(SEP)
                print(f"  t = {frame.timestamp:.3f}")
                print(SEP)

                if canvas is None or not canvas.is_valid():
                    print("  Canvas: NO DATA (check markers in Vicon Tracker)")
                else:
                    print(f"  Canvas  {canvas.width_mm:.1f} mm × {canvas.height_mm:.1f} mm")
                    labels = ("TL", "TR", "BR", "BL")
                    for label, corner in zip(labels, canvas.corners):
                        cx, cy, cz = corner
                        print(f"    {label}  ({cx:+8.1f}, {cy:+8.1f}, {cz:+8.1f}) mm")
                    xx, xy, xz = canvas.x_axis
                    yx, yy, yz = canvas.y_axis
                    nx, ny, nz = canvas.normal
                    print(f"  x_axis  ({xx:.3f}, {xy:.3f}, {xz:.3f})")
                    print(f"  y_axis  ({yx:.3f}, {yy:.3f}, {yz:.3f})")
                    print(f"  normal  ({nx:.3f}, {ny:.3f}, {nz:.3f})")
                    dot = float(np.dot(canvas.x_axis, canvas.y_axis))
                    ok = "\033[92mOK\033[0m" if abs(dot) < 0.01 else "\033[91mWARN\033[0m"
                    print(f"  axes orthogonal?  dot(x,y) = {dot:.4f}  {ok}")

                    # Example: project canvas centre back to world
                    centre_world = canvas.uv_to_world(0.5, 0.5)
                    print(f"  centre  ({centre_world[0]:+.1f}, {centre_world[1]:+.1f}, {centre_world[2]:+.1f}) mm")

                print()
                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\nStopped.")


class _MockCanvasClient(MockViconClient):
    """MockViconClient that also includes synthetic canvas markers."""

    _CORNERS_MM = [
        np.array([0.0,    0.0,    0.0]),   # TL
        np.array([600.0,  0.0,    0.0]),   # TR
        np.array([600.0, -400.0,  0.0]),   # BR
        np.array([0.0,   -400.0,  0.0]),   # BL
    ]

    def _build_frame(self, t):
        frame = super()._build_frame(t)
        # Add four canvas markers under the "canvas" subject
        canvas_body = RigidBody(
            name="canvas",
            position=np.array([300.0, -200.0, 0.0]),
            rotation_quat=np.array([0.0, 0.0, 0.0, 1.0]),
            markers=[
                Marker(name=f"canvas{i+1}", position=c.copy())
                for i, c in enumerate(self._CORNERS_MM)
            ],
        )
        frame.subjects["canvas"] = canvas_body
        for i, corner in enumerate(self._CORNERS_MM):
            mname = f"canvas{i+1}"
            frame.markers[f"canvas/{mname}"] = Marker(
                name=mname, position=corner.copy()
            )
        return frame


if __name__ == "__main__":
    main()
