"""
Record all tracked subjects to a CSV file.

Each row: timestamp, subject_name, x_mm, y_mm, z_mm, qx, qy, qz, qw, occluded

Usage:
    python examples/record_csv.py --host 192.168.1.10:801 --out recording.csv
    python examples/record_csv.py --mock --duration 5 --out recording.csv
"""

import argparse
import csv
import sys
import time

from vicon_sdk import MockViconClient, ViconClient

FIELDS = ["timestamp", "subject", "x_mm", "y_mm", "z_mm", "qx", "qy", "qz", "qw", "occluded"]


def main():
    ap = argparse.ArgumentParser(description="Record Vicon subjects to CSV")
    ap.add_argument("--host", default="localhost:801")
    ap.add_argument("--mock", action="store_true", help="Use simulated data")
    ap.add_argument("--out", default="recording.csv", metavar="FILE")
    ap.add_argument("--rate", type=float, default=100.0, help="Capture rate Hz (default: 100)")
    ap.add_argument("--duration", type=float, default=None,
                    help="Stop after this many seconds (default: run until Ctrl-C)")
    args = ap.parse_args()

    client = MockViconClient() if args.mock else ViconClient(args.host)
    interval = 1.0 / args.rate

    print(f"Recording to {args.out} at {args.rate:.0f} Hz …  Ctrl-C to stop.")
    if args.duration:
        print(f"Will stop after {args.duration:.1f} s.")

    rows_written = 0
    start_time = None

    with client, open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()

        # Wait for first frame
        deadline = time.time() + 5.0
        while client.latest_frame is None and time.time() < deadline:
            time.sleep(0.05)
        if client.latest_frame is None:
            raise SystemExit("No frames received.")

        start_time = time.time()
        last_ts = None

        try:
            while True:
                frame = client.latest_frame
                if frame is None or frame.timestamp == last_ts:
                    time.sleep(interval)
                    continue

                last_ts = frame.timestamp

                for name, body in frame.subjects.items():
                    px, py, pz = body.position
                    qx, qy, qz, qw = body.rotation_quat
                    writer.writerow({
                        "timestamp": f"{frame.timestamp:.6f}",
                        "subject":   name,
                        "x_mm":      f"{px:.3f}",
                        "y_mm":      f"{py:.3f}",
                        "z_mm":      f"{pz:.3f}",
                        "qx":        f"{qx:.6f}",
                        "qy":        f"{qy:.6f}",
                        "qz":        f"{qz:.6f}",
                        "qw":        f"{qw:.6f}",
                        "occluded":  int(body.occluded),
                    })
                    rows_written += 1

                fh.flush()

                elapsed = time.time() - start_time
                if args.duration and elapsed >= args.duration:
                    break

                time.sleep(interval)

        except KeyboardInterrupt:
            pass

    elapsed = time.time() - start_time
    print(f"Saved {rows_written} rows in {elapsed:.1f} s  →  {args.out}")


if __name__ == "__main__":
    main()
