"""Intel RealSense D455 adapter (camera.md SDK install). pyrealsense2 is an
optional dependency installed on the edge board; the import is guarded so the
MVP runs on a dev machine without the SDK. Repo moved IntelRealSense ->
realsenseai in mid-2025; source-build pyrealsense2 together with librealsense2
(-DBUILD_PYTHON_BINDINGS=ON) to avoid silent ABI mismatch."""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..common.clock import monotonic_ms, timestamp_ms
from .interface import CameraConfig, DepthFrame, DeviceInfo, IDepthCamera

try:
    import pyrealsense2 as rs  # type: ignore
    _HAVE_RS = True
except Exception:  # noqa: BLE001
    rs = None  # type: ignore
    _HAVE_RS = False


class RealSenseCamera(IDepthCamera):
    def __init__(self) -> None:
        if not _HAVE_RS:
            raise RuntimeError(
                "pyrealsense2 not installed. Install with `pip install .[realsense]` "
                "or source-build librealsense with -DBUILD_PYTHON_BINDINGS=ON."
            )
        self._pipeline = None
        self._profile = None
        self._cfg: Optional[CameraConfig] = None
        self._frame_id = 0
        self._depth_scale_m = 0.001

    def open(self, cfg: CameraConfig) -> bool:
        self._cfg = cfg
        self._pipeline = rs.pipeline()
        rs_cfg = rs.config()
        if cfg.serial and cfg.serial != "auto":
            rs_cfg.enable_device(cfg.serial)
        rs_cfg.enable_stream(rs.stream.depth, cfg.width, cfg.height,
                             rs.format.z16, cfg.fps)
        self._profile = self._pipeline.start(rs_cfg)
        depth_sensor = self._profile.get_device().first_depth_sensor()
        self._depth_scale_m = float(depth_sensor.get_depth_scale())
        return True

    def close(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None

    def is_connected(self) -> bool:
        return self._pipeline is not None

    def usb_speed(self) -> str:
        # camera.md: silent USB 2.0 fallback kills FPS. Report the negotiated speed.
        if self._profile is None:
            return "unknown"
        try:
            dev = self._profile.get_device()
            return str(dev.get_info(rs.camera_info.usb_type_descriptor))
        except Exception:  # noqa: BLE001
            return "unknown"

    def get_device_info(self) -> DeviceInfo:
        dev = self._profile.get_device()
        info = rs.camera_info
        return DeviceInfo(
            vendor="intel_realsense",
            model=dev.get_info(info.name),
            serial=dev.get_info(info.serial_number),
            firmware=dev.get_info(info.firmware_version),
            sdk_version=rs.__version__ if hasattr(rs, "__version__") else "librealsense2",
        )

    def get_frame(self, timeout_ms: int) -> Optional[DepthFrame]:
        if self._pipeline is None:
            return None
        try:
            frames = self._pipeline.wait_for_frames(timeout_ms)
        except RuntimeError:
            return None  # timeout
        depth = frames.get_depth_frame()
        if not depth:
            return None
        data = np.asanyarray(depth.get_data()).astype(np.uint16)
        self._frame_id += 1
        return DepthFrame(
            timestamp_ms=timestamp_ms(),
            monotonic_ms=monotonic_ms(),
            frame_id=self._frame_id,
            width=data.shape[1], height=data.shape[0],
            depth_scale_m=self._depth_scale_m,
            data=data,
        )
