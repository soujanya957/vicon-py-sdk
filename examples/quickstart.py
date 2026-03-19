"""
quickstart.py — runs with zero setup (no hardware, no SDK library needed).

Shows the full API using MockViconClient: streaming, subject lookup,
canvas tracking, and UV coordinate conversion.

Run:
    python examples/quickstart.py
"""

import time
import numpy as np
from vicon_sdk import MockViconClient, CanvasFrame, sort_corners
from vicon_sdk.types import RigidBody, Marker

# ---------------------------------------------------------------------------
# Set up a mock scene: a robot and a flat canvas
# ---------------------------------------------------------------------------

class DemoScene(MockViconClient):
    """
    Simulates:
      - "robot"  : orbits the origin slowly
      - "target" : stationary rigid body
      - "canvas" : four corner markers defining a 600×400 mm flat surface
    """
    _CORNERS = [
        np.array([200.0,   0.0, 0.0]),   # TL
        np.array([800.0,   0.0, 0.0]),   # TR
        np.array([800.0, 400.0, 0.0]),   # BR
        np.array([200.0, 400.0, 0.0]),   # BL
    ]

    def _build_frame(self, t):
        frame = super()._build_frame(t)

        # Stationary target
        frame.subjects["target"] = RigidBody(
            name="target",
            position=np.array([500.0, 200.0, 0.0]),
            rotation_quat=np.array([0.0, 0.0, 0.0, 1.0]),
        )

        # Canvas markers
        canvas_body = RigidBody(
            name="canvas",
            position=np.mean(self._CORNERS, axis=0),
            rotation_quat=np.array([0.0, 0.0, 0.0, 1.0]),
            markers=[
                Marker(name=f"c{i+1}", position=c.copy())
                for i, c in enumerate(self._CORNERS)
            ],
        )
        frame.subjects["canvas"] = canvas_body
        for i, corner in enumerate(self._CORNERS):
            frame.markers[f"canvas/c{i+1}"] = Marker(
                name=f"c{i+1}", position=corner.copy()
            )
        return frame


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("  vicon-sdk quickstart  (MockViconClient — no hardware)")
    print("=" * 55)
    print()

    with DemoScene(subjects={"robot": np.array([400.0, 0.0, 500.0])}) as client:
        # Wait for first frame
        while client.latest_frame is None:
            time.sleep(0.01)

        print("─── Streaming subjects")
        for _ in range(3):
            frame = client.latest_frame
            print(f"\n  t={frame.timestamp:.2f}   subjects: {frame.subject_names()}")

            robot = frame.subject("robot")
            if robot:
                px, py, pz = robot.position
                print(f"  robot    pos ({px:+7.1f}, {py:+7.1f}, {pz:+7.1f}) mm")

            target = frame.subject("target")
            if target:
                px, py, pz = target.position
                print(f"  target   pos ({px:+7.1f}, {py:+7.1f}, {pz:+7.1f}) mm")

            time.sleep(0.5)

        print()
        print("─── Canvas tracking")
        frame = client.latest_frame

        corners = [frame.marker("canvas", f"c{i+1}").position for i in range(4)]
        canvas = CanvasFrame(sort_corners(corners))

        print(f"  size    {canvas.width_mm:.0f} mm × {canvas.height_mm:.0f} mm")
        print(f"  x_axis  {canvas.x_axis.round(3)}")
        print(f"  y_axis  {canvas.y_axis.round(3)}")
        print(f"  normal  {canvas.normal.round(3)}")

        print()
        print("─── UV coordinate conversion")

        # Project the robot onto the canvas plane
        robot_pos = frame.subject("robot").position
        u, v = canvas.world_to_uv(robot_pos)
        inside = "inside" if 0 <= u <= 1 and 0 <= v <= 1 else "outside"
        print(f"  robot projected to canvas UV: ({u:.3f}, {v:.3f})  [{inside}]")

        # Get the world position of the canvas centre
        centre = canvas.uv_to_world(0.5, 0.5)
        print(f"  canvas centre in world frame: {centre.round(1)} mm")

        # Get a point 50 mm above the canvas centre
        above = canvas.uv_to_world(0.5, 0.5, z_offset_mm=50.0)
        print(f"  50 mm above canvas centre:    {above.round(1)} mm")

        print()
        print("─── RigidBody.rotation_matrix")
        body = frame.subject("robot")
        print(f"  rotation matrix (3×3):")
        for row in body.rotation_matrix:
            print(f"    {row.round(4)}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
