"""
Print all markers (labeled and unlabeled) every second.

Labeled markers are grouped by subject. Unlabeled markers are markers
Vicon can see but hasn't assigned to any subject.

Usage:
    python examples/print_markers.py --host 192.168.1.10:801
    python examples/print_markers.py --mock
"""

import argparse
import time

from vicon_sdk import MockViconClient, ViconClient

SEP = "─" * 60


def main():
    ap = argparse.ArgumentParser(description="Print all Vicon markers each second")
    ap.add_argument("--host", default="localhost:801",
                    help="Vicon DataStream server address")
    ap.add_argument("--mock", action="store_true",
                    help="Use simulated data")
    args = ap.parse_args()

    if args.mock:
        print("Using mock Vicon client.")
        client = MockViconClient()
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
                if frame.frame_number is not None:
                    print(f"  Frame: {frame.frame_number}  |  Rate: {frame.frame_rate:.0f} Hz  |  t = {frame.timestamp:.3f}")
                else:
                    print(f"  t = {frame.timestamp:.3f}")
                print(SEP)

                # Subjects
                n_subjects = len(frame.subjects)
                print(f"  Subjects ({n_subjects}):")
                for name, body in sorted(frame.subjects.items()):
                    x, y, z = body.position
                    occ = " (occluded)" if body.occluded else ""
                    print(f"    {name}{occ}")
                    print(f"      position  ({x:+8.1f}, {y:+8.1f}, {z:+8.1f}) mm")

                # Unlabeled markers
                n_unlab = len(frame.unlabeled_markers)
                print(f"  Unlabeled Markers ({n_unlab}):")
                for i, m in enumerate(frame.unlabeled_markers):
                    x, y, z = m.position
                    print(f"    Marker #{i}: ({x:.2f}, {y:.2f}, {z:.2f})")

                # Labeled markers grouped by subject
                by_subject: dict = {}
                for key, marker in frame.markers.items():
                    subject = key.split("/")[0] if "/" in key else key
                    by_subject.setdefault(subject, []).append(marker)

                n_labeled = sum(len(v) for v in by_subject.values())
                print(f"  Labeled Markers ({n_labeled}):")
                for subject, markers in sorted(by_subject.items()):
                    print(f"    [{subject}]")
                    for m in markers:
                        x, y, z = m.position
                        occ = " (occluded)" if m.occluded else ""
                        print(f"      {m.name:<20} ({x:+8.1f}, {y:+8.1f}, {z:+8.1f}) mm{occ}")

                print()
                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
