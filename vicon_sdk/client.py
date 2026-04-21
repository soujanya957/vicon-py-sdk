"""
vicon_sdk.client
================
Two implementations of the Vicon streaming client sharing a common interface:

  ViconClient      — wraps the official Vicon C SDK via ctypes (vicon_sdk/sdk.py).
                     Connects to a live Vicon DataStream server and streams frames
                     on a background thread at whatever rate the server delivers.

  MockViconClient  — generates synthetic data for testing without any hardware.
                     Simulates one or more configurable rigid bodies.

Both are thread-safe: a background thread continuously pulls frames and stores
the latest one.  Consumers read ``client.latest_frame`` from any thread.

Usage
-----
::

    from vicon_sdk import ViconClient

    client = ViconClient("192.168.1.10:801")
    client.start()

    frame = client.latest_frame          # ViconFrame | None
    body  = frame.subject("my_robot")    # RigidBody  | None
    if body and not body.occluded:
        print(body.position)             # [x, y, z] in mm

    client.stop()

Context manager
---------------
::

    with ViconClient("192.168.1.10:801") as client:
        ...  # client.start() / stop() called automatically

Waiting for the first frame
---------------------------
::

    import time
    client.start()
    deadline = time.time() + 5.0
    while client.latest_frame is None and time.time() < deadline:
        time.sleep(0.05)
    if client.latest_frame is None:
        raise RuntimeError("No frames received from Vicon")
"""

from __future__ import annotations

import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import numpy as np

from .types import CanvasFrame, Marker, RigidBody, ViconFrame

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class ViconClientBase(ABC):
    """Thread-safe base class for ViconClient and MockViconClient."""

    def __init__(self) -> None:
        self._frame: Optional[ViconFrame] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def latest_frame(self) -> Optional[ViconFrame]:
        """The most recent frame, or None if no frame has been received yet."""
        with self._lock:
            return self._frame

    def start(self) -> None:
        """Start the background streaming thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=self.__class__.__name__
        )
        self._thread.start()
        logger.info("[Vicon] %s started.", self.__class__.__name__)

    def stop(self) -> None:
        """Stop the background thread and disconnect."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("[Vicon] %s stopped.", self.__class__.__name__)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ── internal ─────────────────────────────────────────────────────────────

    def _set_frame(self, frame: ViconFrame) -> None:
        with self._lock:
            self._frame = frame

    @abstractmethod
    def _run(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Real client
# ---------------------------------------------------------------------------


class ViconClient(ViconClientBase):
    """
    Live Vicon DataStream client.

    Connects to the Vicon server, streams frames at the server's capture rate
    (typically 100 Hz or 250 Hz), and exposes each frame as a :class:`ViconFrame`
    containing **all** tracked subjects in the current Vicon scene.

    Args:
        host: Vicon DataStream server address, e.g. ``"192.168.1.10:801"``.
    """

    def __init__(self, host: str = "localhost:801") -> None:
        super().__init__()
        self.host = host

    def _run(self) -> None:
        from .sdk import ViconSDKClient, SUCCESS, CLIENT_PULL

        logger.info("[Vicon] Connecting to %s …", self.host)
        client = ViconSDKClient()
        r = client.connect(self.host)
        if r != SUCCESS:
            raise RuntimeError(
                f"Vicon connect failed (result={r}).\n"
                f"Make sure the Vicon DataStream server is running and reachable at {self.host}."
            )
        client.enable_segment_data()
        client.enable_marker_data()
        client.enable_unlabeled_marker_data()
        client.set_stream_mode(CLIENT_PULL)
        logger.info("[Vicon] Connected to %s.", self.host)

        while self._running:
            if client.get_frame() != SUCCESS:
                time.sleep(0.002)
                continue
            self._set_frame(self._parse_frame(client, time.time()))

        client.disconnect()
        client.destroy()
        logger.info("[Vicon] Disconnected.")

    def _parse_frame(self, client, ts: float) -> ViconFrame:
        subjects: Dict[str, RigidBody] = {}
        markers: Dict[str, Marker] = {}

        n_subjects = client.get_subject_count()
        for i in range(n_subjects):
            name = client.get_subject_name(i)
            if name is None:
                continue
            body = self._get_rigid_body(client, name)
            if body is not None:
                subjects[name] = body
                for m in body.markers:
                    markers[f"{name}/{m.name}"] = m

        # Unlabeled markers — markers Vicon can see but hasn't assigned to a subject
        unlabeled: List[Marker] = []
        n_unlab = client.get_unlabeled_marker_count()
        for i in range(n_unlab):
            pos, occ = client.get_unlabeled_marker_global_translation(i)
            if pos is not None:
                unlabeled.append(Marker(name=f"unlabeled_{i}",
                                        position=np.array(pos, dtype=float),
                                        occluded=bool(occ)))

        return ViconFrame(timestamp=ts, subjects=subjects, markers=markers,
                          unlabeled_markers=unlabeled,
                          frame_number=client.get_frame_number(),
                          frame_rate=client.get_frame_rate())

    def _get_rigid_body(self, client, subject: str) -> Optional[RigidBody]:
        trans, occ = client.get_segment_global_translation(subject, subject)
        if trans is None:
            return None
        rot, _ = client.get_segment_global_rotation_quaternion(subject, subject)
        if rot is None:
            return None

        mlist: List[Marker] = []
        n = client.get_marker_count(subject)
        for i in range(n):
            mname = client.get_marker_name(subject, i)
            if mname is None:
                continue
            mpos, mocc = client.get_marker_global_translation(subject, mname)
            if mpos is not None:
                mlist.append(Marker(name=mname,
                                    position=np.array(mpos, dtype=float),
                                    occluded=bool(mocc)))

        quality = client.get_object_quality(subject)  # None if unavailable

        return RigidBody(
            name=subject,
            position=np.array(trans, dtype=float),
            rotation_quat=np.array(rot, dtype=float),
            markers=mlist,
            occluded=bool(occ),
            quality=quality,
        )


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------


class MockViconClient(ViconClientBase):
    """
    Simulated Vicon client for testing without any hardware.

    By default, simulates a single rigid body called ``"object"`` that orbits
    the origin in the XY plane at 0.1 Hz.  You can replace this with any
    subjects you like by subclassing and overriding :meth:`_build_frame`.

    Args:
        rate_hz:  Simulated capture rate in Hz (default: 100).
        subjects: Optional mapping of ``{name: initial_position_mm}`` for the
                  subjects to simulate.  If not provided, uses a single
                  ``"object"`` subject.

    Example — custom subjects::

        mock = MockViconClient(
            subjects={
                "robot":  np.array([0.0,   0.0, 500.0]),
                "target": np.array([800.0, 0.0, 200.0]),
            }
        )
        mock.start()
    """

    RATE_HZ: int = 100

    def __init__(
        self,
        rate_hz: int = 100,
        subjects: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        super().__init__()
        self.rate_hz = rate_hz
        self._subjects = subjects or {"object": np.array([0.0, 0.0, 500.0])}

    def _run(self) -> None:
        dt = 1.0 / self.rate_hz
        t = 0.0
        while self._running:
            t += dt
            self._set_frame(self._build_frame(t))
            time.sleep(dt)

    def _build_frame(self, t: float) -> ViconFrame:
        """
        Build a synthetic frame.  Override this method to provide custom
        motion patterns.  *t* is elapsed time in seconds.
        """
        subjects: Dict[str, RigidBody] = {}
        for name, base_pos in self._subjects.items():
            # Slow circular orbit in XY, stationary Z
            angle = 2 * math.pi * 0.1 * t
            r = float(np.linalg.norm(base_pos[:2])) or 200.0
            pos = np.array([
                r * math.cos(angle),
                r * math.sin(angle),
                float(base_pos[2]),
            ])
            # Yaw matches the orbit
            quat = np.array([0.0, 0.0, math.sin(angle / 2), math.cos(angle / 2)])
            subjects[name] = RigidBody(
                name=name,
                position=pos,
                rotation_quat=quat,
            )
        return ViconFrame(timestamp=time.time(), subjects=subjects)
