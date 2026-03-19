"""
Print all tracked subjects and their poses once per second.

Usage:
    python examples/print_subjects.py --host 192.168.1.10:801
    python examples/print_subjects.py --mock
"""

import argparse
import time

from vicon_sdk import MockViconClient, ViconClient

SEP = "─" * 60


def main():
    ap = argparse.ArgumentParser(description="Stream and print all Vicon subjects")
    ap.add_argument("--host", default="localhost:801",
                    help="Vicon DataStream server address (default: localhost:801)")
    ap.add_argument("--mock", action="store_true",
                    help="Use simulated data instead of live hardware")
    ap.add_argument("--rate", type=float, default=1.0,
                    help="Print rate in Hz (default: 1.0)")
    args = ap.parse_args()

    if args.mock:
        print("Using mock Vicon client (no hardware required).")
        client = MockViconClient()
    else:
        print(f"Connecting to Vicon at {args.host} …")
        client = ViconClient(args.host)

    with client:
        # Wait up to 5 s for the first frame
        deadline = time.time() + 5.0
        while client.latest_frame is None and time.time() < deadline:
            time.sleep(0.05)

        frame = client.latest_frame
        if frame is None:
            raise SystemExit("No frames received — check connection.")

        print("Connected.\n")
        interval = 1.0 / args.rate

        try:
            while True:
                frame = client.latest_frame
                if frame is None:
                    time.sleep(interval)
                    continue

                print(SEP)
                print(f"  t = {frame.timestamp:.3f}   subjects: {len(frame.subjects)}")
                print(SEP)

                if not frame.subjects:
                    print("  (no subjects tracked)")
                else:
                    for name, body in frame.subjects.items():
                        status = "OCCLUDED" if body.occluded else "OK"
                        px, py, pz = body.position
                        qx, qy, qz, qw = body.rotation_quat
                        print(f"  {name:<20}  [{status}]")
                        print(f"    pos   ({px:+9.1f}, {py:+9.1f}, {pz:+9.1f}) mm")
                        print(f"    quat  qx={qx:.3f}  qy={qy:.3f}  qz={qz:.3f}  qw={qw:.3f}")
                        if body.markers:
                            print(f"    markers  {len(body.markers)}")
                        print()

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
