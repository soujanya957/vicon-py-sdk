"""
vicon-sdk — Python client for the Vicon DataStream SDK
=======================================================
A lightweight, thread-safe Python client for streaming motion-capture data
from a Vicon system using the official Vicon DataStream C SDK.

Quick start::

    from vicon_sdk import ViconClient

    with ViconClient("192.168.1.10:801") as client:
        import time
        time.sleep(0.5)                      # wait for first frame
        frame = client.latest_frame
        body  = frame.subject("my_robot")
        if body:
            print(body.position)             # [x, y, z] mm

Without hardware::

    from vicon_sdk import MockViconClient
    import numpy as np

    with MockViconClient(subjects={"robot": np.array([500, 0, 200])}) as client:
        import time; time.sleep(0.1)
        frame = client.latest_frame
        print(frame.subject_names())
"""

from .types import (
    CanvasFrame,
    Marker,
    RigidBody,
    ViconFrame,
    sort_corners,
)
from .client import ViconClient, MockViconClient

__all__ = [
    # Clients
    "ViconClient",
    "MockViconClient",
    # Data types
    "ViconFrame",
    "RigidBody",
    "Marker",
    "CanvasFrame",
    # Utilities
    "sort_corners",
]

__version__ = "0.1.0"
