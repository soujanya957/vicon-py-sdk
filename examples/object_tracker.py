"""
Track any named Vicon subject (rigid body) and print its position and
orientation every second.

Usage:
    python examples/object_tracker.py --host 192.168.1.10:801 --object wand
    python examples/object_tracker.py --mock --object object
"""

import argparse
import time

from vicon_sdk import MockViconClient, ViconClient

SEP = "─" * 60


def main():
    ap = argparse.ArgumentParser(
        description="Track a named Vicon subject by position/orientation"
    )
    ap.add_argument(
        "--host", default="localhost:801", help="Vicon DataStream server address"
    )
    ap.add_argument("--mock", action="store_true", help="Use simulated data")
    ap.add_argument(
        "--object",
        dest="object_name",
        required=True,
        metavar="NAME",
        help="Vicon subject name to track (e.g. wand)",
    )
    args = ap.parse_args()

    if args.mock:
        print("Using mock Vicon client.")
        client = MockViconClient(subjects={args.object_name: [0.0, 0.0, 500.0]})
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

                print(SEP)
                print(f"  t = {frame.timestamp:.3f}")
                print(SEP)

                body = frame.subjects.get(args.object_name)
                if body is None or body.occluded:
                    print(
                        f"  {args.object_name}: NO DATA (check subject in Vicon Tracker)"
                    )
                else:
                    x, y, z = body.position
                    qx, qy, qz, qw = body.rotation_quat
                    print(f"  position  ({x:+8.1f}, {y:+8.1f}, {z:+8.1f}) mm")
                    print(
                        f"  rotation  qx={qx:.4f}  qy={qy:.4f}  qz={qz:.4f}  qw={qw:.4f}"
                    )
                    if body.quality is not None:
                        print(f"  quality   {body.quality:.2f}")

                print()
                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
