"""
vicon_sdk.types
===============
Data classes for every kind of object tracked by Vicon.

Marker
    A single retroreflective marker — just a position (and an occlusion flag).

RigidBody
    A named subject with a solved 6-DoF pose (position + quaternion) plus its
    individual marker positions.  Exposes a ``rotation_matrix`` property for
    convenience.

ViconFrame
    One complete snapshot from Vicon at a given timestamp.  Contains a
    dictionary of all tracked subjects and a dictionary of all tracked
    individual markers from those subjects.  Look up by subject name::

        frame.subject("my_robot")   # → RigidBody | None
        frame.marker("my_robot", "marker_1")  # → Marker | None

CanvasFrame
    A planar surface defined by exactly four corner markers in TL / TR / BR / BL
    order.  Exposes the local coordinate frame (x_axis, y_axis, normal), the
    physical dimensions (width_mm, height_mm), and UV ↔ world-frame conversions.

    Useful whenever you track a flat target (whiteboard, floor tile, table) with
    four retroreflective markers and need to work in that surface's local frame.

All positions are in **millimetres** in the Vicon world frame unless noted.
Quaternions are stored as ``[qx, qy, qz, qw]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


@dataclass
class Marker:
    """A single retroreflective marker."""

    name: str
    position: np.ndarray  # shape (3,) — [x, y, z] in mm
    occluded: bool = False


@dataclass
class RigidBody:
    """
    A named Vicon subject with a solved 6-DoF pose.

    Attributes
    ----------
    name           : subject name as configured in Vicon Tracker / Nexus
    position       : shape (3,) — [x, y, z] in mm, Vicon world frame
    rotation_quat  : shape (4,) — [qx, qy, qz, qw]
    markers        : individual markers belonging to this subject
    occluded       : True if the pose solution was unavailable this frame
    """

    name: str
    position: np.ndarray
    rotation_quat: np.ndarray
    markers: List[Marker] = field(default_factory=list)
    occluded: bool = False

    @property
    def rotation_matrix(self) -> np.ndarray:
        """Return the 3×3 rotation matrix (world ← body) from the stored quaternion."""
        qx, qy, qz, qw = self.rotation_quat
        return np.array(
            [
                [1 - 2 * (qy**2 + qz**2), 2 * (qx*qy - qz*qw), 2 * (qx*qz + qy*qw)],
                [2 * (qx*qy + qz*qw), 1 - 2 * (qx**2 + qz**2), 2 * (qy*qz - qx*qw)],
                [2 * (qx*qz - qy*qw), 2 * (qy*qz + qx*qw), 1 - 2 * (qx**2 + qy**2)],
            ],
            dtype=float,
        )

    def marker_by_name(self, name: str) -> Optional[Marker]:
        """Return the marker with the given name, or None."""
        for m in self.markers:
            if m.name == name:
                return m
        return None


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------


@dataclass
class ViconFrame:
    """
    One complete snapshot from the Vicon system.

    Attributes
    ----------
    timestamp : Unix timestamp (seconds) of when the frame was captured.
    subjects  : All tracked rigid-body subjects, keyed by subject name.
    markers   : All individual markers across all subjects, keyed by
                ``"subject_name/marker_name"``.

    Usage
    -----
    ::

        frame = client.latest_frame

        # Get a rigid body
        body = frame.subject("my_robot")
        if body and not body.occluded:
            print(body.position)

        # Get an individual marker
        tip = frame.marker("my_robot", "tip_marker")
    """

    timestamp: float
    subjects: Dict[str, RigidBody] = field(default_factory=dict)
    markers: Dict[str, Marker] = field(default_factory=dict)  # key: "subject/marker"

    def subject(self, name: str) -> Optional[RigidBody]:
        """Return the RigidBody with *name*, or None if not tracked this frame."""
        return self.subjects.get(name)

    def marker(self, subject: str, marker: str) -> Optional[Marker]:
        """Return a specific marker by subject and marker name, or None."""
        return self.markers.get(f"{subject}/{marker}")

    def subject_names(self) -> List[str]:
        """Return all subject names present in this frame."""
        return list(self.subjects.keys())


# ---------------------------------------------------------------------------
# CanvasFrame — planar surface utility
# ---------------------------------------------------------------------------


@dataclass
class CanvasFrame:
    """
    A flat planar surface defined by exactly four corner markers.

    The four corners must be provided in this order::

        corners[0] — Top-Left  (TL)  — origin of the local 2-D frame
        corners[1] — Top-Right (TR)  — defines +x_axis (width direction)
        corners[2] — Bottom-Right (BR)
        corners[3] — Bottom-Left  (BL) — defines +y_axis (height direction)

    Local coordinate system
    -----------------------
    ::

        origin = TL corner
        x_axis = unit vector TL → TR    (width direction,  U axis)
        y_axis = unit vector TL → BL    (height direction, V axis)
        normal = x_axis × y_axis        (points away from the canvas face)

    UV coordinates are normalised: (0, 0) = TL, (1, 1) = BR.

    Example
    -------
    ::

        from vicon_sdk import ViconClient, CanvasFrame
        import numpy as np

        # Build a CanvasFrame from four Vicon markers
        corners = [frame.marker("canvas", f"corner{i+1}").position for i in range(4)]
        canvas = CanvasFrame(sort_corners(corners))

        # Convert a world-frame point to canvas UV
        u, v = canvas.world_to_uv(point_mm)

        # Project a UV coordinate back to world frame
        world_pt = canvas.uv_to_world(0.5, 0.5)  # centre of canvas
    """

    corners: List[np.ndarray]  # 4 × shape(3,), in mm

    # ── axes ─────────────────────────────────────────────────────────────────

    @property
    def origin(self) -> np.ndarray:
        return self.corners[0]

    @property
    def x_axis(self) -> np.ndarray:
        """Unit vector along the canvas width (TL → TR)."""
        v = self.corners[1] - self.corners[0]
        return v / np.linalg.norm(v)

    @property
    def y_axis(self) -> np.ndarray:
        """Unit vector along the canvas height (TL → BL)."""
        v = self.corners[3] - self.corners[0]
        return v / np.linalg.norm(v)

    @property
    def normal(self) -> np.ndarray:
        """Unit normal pointing away from the canvas surface."""
        n = np.cross(self.x_axis, self.y_axis)
        return n / np.linalg.norm(n)

    @property
    def center(self) -> np.ndarray:
        """Centre of the canvas in world frame (mm)."""
        return np.mean(np.array(self.corners), axis=0)

    # ── dimensions ───────────────────────────────────────────────────────────

    @property
    def width_mm(self) -> float:
        return float(np.linalg.norm(self.corners[1] - self.corners[0]))

    @property
    def height_mm(self) -> float:
        return float(np.linalg.norm(self.corners[3] - self.corners[0]))

    def is_valid(self) -> bool:
        return len(self.corners) == 4 and self.width_mm > 1.0 and self.height_mm > 1.0

    # ── coordinate conversions ───────────────────────────────────────────────

    def world_to_uv(self, point_mm: np.ndarray) -> Tuple[float, float]:
        """
        Orthographically project *point_mm* onto the canvas plane and return
        normalised UV coordinates.  Values outside [0, 1] are outside the canvas.
        """
        local = point_mm - self.origin
        u = float(np.dot(local, self.x_axis)) / self.width_mm
        v = float(np.dot(local, self.y_axis)) / self.height_mm
        return u, v

    def uv_to_world(self, u: float, v: float, z_offset_mm: float = 0.0) -> np.ndarray:
        """
        Convert canvas UV coordinates to Vicon world-frame position (mm).

        Args:
            u, v:          Normalised canvas coordinates [0, 1].
            z_offset_mm:   Lift above canvas surface along the normal
                           (positive = away from canvas face).
        """
        return (
            self.origin
            + u * self.width_mm * self.x_axis
            + v * self.height_mm * self.y_axis
            + z_offset_mm * self.normal
        )

    def distance_to_mm(self, point_mm: np.ndarray) -> float:
        """
        Signed distance from *point_mm* to the canvas plane (mm).
        Positive → on the side the normal points toward (above the surface).
        """
        return float(np.dot(point_mm - self.origin, self.normal))


# ---------------------------------------------------------------------------
# Utility: sort four unsorted corner markers into TL / TR / BR / BL order
# ---------------------------------------------------------------------------


def sort_corners(pts: List[np.ndarray]) -> List[np.ndarray]:
    """
    Sort four unordered corner points into [TL, TR, BR, BL] order.

    Assumes the canvas lies roughly in the XY plane (Z ≈ constant) and that
    +X is the width direction and +Y is the height direction in the Vicon
    world frame.  Works for any marker-naming convention.

    Args:
        pts: List of 4 arrays, each shape (3,), in mm.

    Returns:
        [TL, TR, BR, BL] sorted list.
    """
    if len(pts) != 4:
        raise ValueError(f"Expected 4 corners, got {len(pts)}")
    by_x = sorted(pts, key=lambda p: p[0])
    left = sorted(by_x[:2], key=lambda p: p[1])   # low-Y then high-Y
    right = sorted(by_x[2:], key=lambda p: p[1])  # low-Y then high-Y
    return [left[0], right[0], right[1], left[1]]  # TL, TR, BR, BL
