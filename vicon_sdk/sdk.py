"""
vicon_sdk.sdk
=============
ctypes wrapper around the official Vicon DataStream C SDK shared library.

The library is searched for in this order:
  1. Next to this file  (drop it alongside sdk.py)
  2. Directory pointed to by the ``VICON_SDK_PATH`` environment variable
  3. Platform-specific default install locations

Platform support
----------------
  macOS   — libViconDataStreamSDK_C.dylib
  Linux   — libViconDataStreamSDK_C.so
  Windows — ViconDataStreamSDK_C.dll

You do NOT need the full Vicon DataStream SDK Python bindings — just the
compiled C shared library from the official SDK download.

Result enum (from IDataStreamClientBase.h)
------------------------------------------
  Unknown=0, NotImplemented=1, Success=2, InvalidHostName=3, ...

Stream modes
------------
  CLIENT_PULL          (0) — poll the server for new frames
  CLIENT_PULL_PREFETCH (1) — pre-fetch frames on a background thread
  SERVER_PUSH          (2) — server streams frames as fast as it captures
"""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Library location
# ---------------------------------------------------------------------------

_SYSTEM = platform.system()

if _SYSTEM == "Darwin":
    _LIB_NAME = "libViconDataStreamSDK_C.dylib"
    _DEFAULT_PATHS: List[Path] = [
        Path.home() / "Downloads" / "ViconDataStreamSDK_1.13.0+167154h"
        / "ViconDataStreamSDK_1.13.0+167154h_Mac" / "Mac" / _LIB_NAME,
    ]
elif _SYSTEM == "Linux":
    _LIB_NAME = "libViconDataStreamSDK_C.so"
    _DEFAULT_PATHS: List[Path] = [
        Path("/usr/local/lib") / _LIB_NAME,
        Path("/opt/vicon") / _LIB_NAME,
    ]
else:  # Windows
    _LIB_NAME = "ViconDataStreamSDK_C.dll"
    _DEFAULT_PATHS: List[Path] = [
        Path("C:/Program Files/Vicon/DataStream SDK") / _LIB_NAME,
    ]

_SEARCH_PATHS: List[Path] = (
    [Path(__file__).parent / _LIB_NAME]
    + ([Path(os.environ["VICON_SDK_PATH"]) / _LIB_NAME]
       if os.environ.get("VICON_SDK_PATH") else [])
    + _DEFAULT_PATHS
)

_lib: Optional[ctypes.CDLL] = None


def _load_lib() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib
    for p in _SEARCH_PATHS:
        if p.exists():
            _lib = ctypes.CDLL(str(p))
            _configure(_lib)
            return _lib
    searched = "\n  ".join(str(p) for p in _SEARCH_PATHS)
    raise RuntimeError(
        f"Cannot find {_LIB_NAME}.\n"
        f"Searched:\n  {searched}\n\n"
        "Options:\n"
        f"  1. Copy {_LIB_NAME} next to vicon_sdk/sdk.py\n"
        "  2. Set the VICON_SDK_PATH env var to the directory containing it\n"
        "  3. Download the Vicon DataStream SDK from https://www.vicon.com/software/datastream-sdk/"
    )


# ---------------------------------------------------------------------------
# Output structs  (ABI-matched to the C SDK)
# ---------------------------------------------------------------------------


class _OutUInt(ctypes.Structure):
    _fields_ = [("Result", ctypes.c_int), ("Value", ctypes.c_uint)]


class _OutTranslation(ctypes.Structure):
    # _pack_=4: the C SDK uses 4-byte alignment, suppressing the padding
    # that ctypes would normally insert after the 4-byte Result int to
    # align the following double fields on an 8-byte boundary.
    _pack_ = 4
    _fields_ = [
        ("Result", ctypes.c_int),
        ("Translation", ctypes.c_double * 3),
        ("Occluded", ctypes.c_bool),
    ]


class _OutQuaternion(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("Result", ctypes.c_int),
        ("Rotation", ctypes.c_double * 4),
        ("Occluded", ctypes.c_bool),
    ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUCCESS = 2

CLIENT_PULL = 0
CLIENT_PULL_PREFETCH = 1
SERVER_PUSH = 2

_BUF = 256


# ---------------------------------------------------------------------------
# Configure argtypes / restypes
# ---------------------------------------------------------------------------


def _configure(lib: ctypes.CDLL) -> None:
    vp = ctypes.c_void_p
    cp = ctypes.c_char_p
    ui = ctypes.c_uint
    i = ctypes.c_int
    pU = ctypes.POINTER(_OutUInt)
    pT = ctypes.POINTER(_OutTranslation)
    pQ = ctypes.POINTER(_OutQuaternion)

    lib.Client_Create.restype = vp
    lib.Client_Create.argtypes = []
    lib.Client_Destroy.restype = None
    lib.Client_Destroy.argtypes = [vp]
    lib.Client_Connect.restype = i
    lib.Client_Connect.argtypes = [vp, cp]
    lib.Client_Disconnect.restype = i
    lib.Client_Disconnect.argtypes = [vp]

    for name in (
        "EnableSegmentData", "EnableMarkerData", "EnableUnlabeledMarkerData",
        "DisableSegmentData", "DisableMarkerData",
    ):
        f = getattr(lib, f"Client_{name}")
        f.restype = i
        f.argtypes = [vp]

    lib.Client_SetStreamMode.restype = i
    lib.Client_SetStreamMode.argtypes = [vp, i]
    lib.Client_GetFrame.restype = i
    lib.Client_GetFrame.argtypes = [vp]

    lib.Client_GetFrameNumber.restype = None
    lib.Client_GetFrameNumber.argtypes = [vp, pU]

    lib.Client_GetSubjectCount.restype = None
    lib.Client_GetSubjectCount.argtypes = [vp, pU]
    lib.Client_GetSubjectName.restype = i
    lib.Client_GetSubjectName.argtypes = [vp, ui, ui, cp]
    lib.Client_GetSubjectRootSegmentName.restype = i
    lib.Client_GetSubjectRootSegmentName.argtypes = [vp, cp, ui, cp]

    lib.Client_GetSegmentCount.restype = None
    lib.Client_GetSegmentCount.argtypes = [vp, cp, pU]
    lib.Client_GetSegmentName.restype = i
    lib.Client_GetSegmentName.argtypes = [vp, cp, ui, ui, cp]

    lib.Client_GetMarkerCount.restype = None
    lib.Client_GetMarkerCount.argtypes = [vp, cp, pU]
    lib.Client_GetMarkerName.restype = i
    lib.Client_GetMarkerName.argtypes = [vp, cp, ui, ui, cp]

    lib.Client_GetSegmentGlobalTranslation.restype = None
    lib.Client_GetSegmentGlobalTranslation.argtypes = [vp, cp, cp, pT]
    lib.Client_GetMarkerGlobalTranslation.restype = None
    lib.Client_GetMarkerGlobalTranslation.argtypes = [vp, cp, cp, pT]
    lib.Client_GetSegmentGlobalRotationQuaternion.restype = None
    lib.Client_GetSegmentGlobalRotationQuaternion.argtypes = [vp, cp, cp, pQ]


# ---------------------------------------------------------------------------
# High-level Python wrapper
# ---------------------------------------------------------------------------


class ViconSDKClient:
    """
    Thin, Pythonic wrapper around the Vicon DataStream C SDK.

    Supports the context-manager protocol::

        with ViconSDKClient() as c:
            c.connect("192.168.1.10:801")
            c.enable_segment_data()
            c.set_stream_mode(CLIENT_PULL)
            while True:
                if c.get_frame() == SUCCESS:
                    n = c.get_subject_count()
                    ...
    """

    def __init__(self) -> None:
        self._lib = _load_lib()
        self._h = self._lib.Client_Create()
        if not self._h:
            raise RuntimeError("Client_Create() returned null")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.disconnect()
        self.destroy()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def connect(self, host: str) -> int:
        """Connect to a Vicon DataStream server.  Returns result code (SUCCESS=2)."""
        return self._lib.Client_Connect(self._h, host.encode())

    def disconnect(self) -> None:
        self._lib.Client_Disconnect(self._h)

    def destroy(self) -> None:
        self._lib.Client_Destroy(self._h)
        self._h = None

    # ── data types ───────────────────────────────────────────────────────────

    def enable_segment_data(self) -> None:
        self._lib.Client_EnableSegmentData(self._h)

    def enable_marker_data(self) -> None:
        self._lib.Client_EnableMarkerData(self._h)

    def enable_unlabeled_marker_data(self) -> None:
        self._lib.Client_EnableUnlabeledMarkerData(self._h)

    def set_stream_mode(self, mode: int = CLIENT_PULL) -> None:
        self._lib.Client_SetStreamMode(self._h, mode)

    # ── frame ────────────────────────────────────────────────────────────────

    def get_frame(self) -> int:
        """Pull the next frame.  Returns result code."""
        return self._lib.Client_GetFrame(self._h)

    def get_frame_number(self) -> Optional[int]:
        out = _OutUInt()
        self._lib.Client_GetFrameNumber(self._h, ctypes.byref(out))
        return out.Value if out.Result == SUCCESS else None

    # ── subjects ─────────────────────────────────────────────────────────────

    def get_subject_count(self) -> int:
        out = _OutUInt()
        self._lib.Client_GetSubjectCount(self._h, ctypes.byref(out))
        return out.Value if out.Result == SUCCESS else 0

    def get_subject_name(self, index: int) -> Optional[str]:
        buf = ctypes.create_string_buffer(_BUF)
        r = self._lib.Client_GetSubjectName(self._h, index, _BUF, buf)
        return buf.value.decode() if r == SUCCESS else None

    def get_subject_root_segment_name(self, subject: str) -> Optional[str]:
        buf = ctypes.create_string_buffer(_BUF)
        r = self._lib.Client_GetSubjectRootSegmentName(
            self._h, subject.encode(), _BUF, buf
        )
        return buf.value.decode() if r == SUCCESS else None

    # ── segments ─────────────────────────────────────────────────────────────

    def get_segment_count(self, subject: str) -> int:
        out = _OutUInt()
        self._lib.Client_GetSegmentCount(self._h, subject.encode(), ctypes.byref(out))
        return out.Value if out.Result == SUCCESS else 0

    def get_segment_name(self, subject: str, index: int) -> Optional[str]:
        buf = ctypes.create_string_buffer(_BUF)
        r = self._lib.Client_GetSegmentName(
            self._h, subject.encode(), index, _BUF, buf
        )
        return buf.value.decode() if r == SUCCESS else None

    # ── markers ──────────────────────────────────────────────────────────────

    def get_marker_count(self, subject: str) -> int:
        out = _OutUInt()
        self._lib.Client_GetMarkerCount(self._h, subject.encode(), ctypes.byref(out))
        return out.Value if out.Result == SUCCESS else 0

    def get_marker_name(self, subject: str, index: int) -> Optional[str]:
        buf = ctypes.create_string_buffer(_BUF)
        r = self._lib.Client_GetMarkerName(
            self._h, subject.encode(), index, _BUF, buf
        )
        return buf.value.decode() if r == SUCCESS else None

    # ── translations / rotations ─────────────────────────────────────────────

    def get_segment_global_translation(
        self, subject: str, segment: str
    ) -> Tuple[Optional[list], bool]:
        """Returns ([x, y, z] in mm, occluded)."""
        out = _OutTranslation()
        self._lib.Client_GetSegmentGlobalTranslation(
            self._h, subject.encode(), segment.encode(), ctypes.byref(out)
        )
        if out.Result != SUCCESS:
            return None, True
        return list(out.Translation), bool(out.Occluded)

    def get_segment_global_rotation_quaternion(
        self, subject: str, segment: str
    ) -> Tuple[Optional[list], bool]:
        """Returns ([qx, qy, qz, qw], occluded)."""
        out = _OutQuaternion()
        self._lib.Client_GetSegmentGlobalRotationQuaternion(
            self._h, subject.encode(), segment.encode(), ctypes.byref(out)
        )
        if out.Result != SUCCESS:
            return None, True
        return list(out.Rotation), bool(out.Occluded)

    def get_marker_global_translation(
        self, subject: str, marker: str
    ) -> Tuple[Optional[list], bool]:
        """Returns ([x, y, z] in mm, occluded)."""
        out = _OutTranslation()
        self._lib.Client_GetMarkerGlobalTranslation(
            self._h, subject.encode(), marker.encode(), ctypes.byref(out)
        )
        if out.Result != SUCCESS:
            return None, True
        return list(out.Translation), bool(out.Occluded)
