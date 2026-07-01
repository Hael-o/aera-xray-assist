"""Orbbec depth camera adapter (Femto / Gemini families via pyorbbecsdk). Like
the RealSense adapter, pyorbbecsdk is an optional dependency installed only on
the edge board — the import is guarded so the MVP runs on a dev machine without
the SDK. API follows pyorbbecsdk v1/v2 (Pipeline/Config/Context)."""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..common.clock import monotonic_ms, timestamp_ms
from .interface import CameraConfig, DepthFrame, DeviceInfo, IDepthCamera

try:
    from pyorbbecsdk import (  # type: ignore
        Config, Context, OBFormat, OBSensorType, Pipeline,
    )
    _HAVE_OB = True
except Exception:  # noqa: BLE001
    Config = Context = OBFormat = OBSensorType = Pipeline = None  # type: ignore
    _HAVE_OB = False


class OrbbecCamera(IDepthCamera):
    def __init__(self) -> None:
        if not _HAVE_OB:
            raise RuntimeError(
                "pyorbbecsdk not installed. Install with `pip install .[orbbec]` "
                "or build pyorbbecsdk from the OrbbecSDK_Python source."
            )
        self._pipeline = None
        self._cfg: Optional[CameraConfig] = None
        self._info: Optional[DeviceInfo] = None
        self._frame_id = 0
        self._depth_scale_m = 0.001

    def open(self, cfg: CameraConfig) -> bool:
        self._cfg = cfg
        self._pipeline = Pipeline()
        config = Config()
        profiles = self._pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        try:
            profile = profiles.get_video_stream_profile(
                cfg.width, cfg.height, OBFormat.Y16, cfg.fps)
        except Exception:  # noqa: BLE001
            profile = profiles.get_default_video_stream_profile()
        config.enable_stream(profile)
        self._pipeline.start(config)
        dev = self._pipeline.get_device()
        di = dev.get_device_info()
        self._info = DeviceInfo(
            vendor="orbbec",
            model=di.get_name(),
            serial=di.get_serial_number(),
            firmware=di.get_firmware_version(),
            sdk_version="pyorbbecsdk",
        )
        return True

    def close(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None

    def is_connected(self) -> bool:
        return self._pipeline is not None

    def usb_speed(self) -> str:
        if self._pipeline is None:
            return "unknown"
        try:
            di = self._pipeline.get_device().get_device_info()
            return str(di.get_usb_type())
        except Exception:  # noqa: BLE001
            return "unknown"

    def get_device_info(self) -> DeviceInfo:
        return self._info or DeviceInfo(vendor="orbbec", model="unknown", serial="unknown")

    def get_frame(self, timeout_ms: int) -> Optional[DepthFrame]:
        if self._pipeline is None:
            return None
        frames = self._pipeline.wait_for_frames(timeout_ms)
        if frames is None:
            return None  # timeout
        depth = frames.get_depth_frame()
        if depth is None:
            return None
        h, w = depth.get_height(), depth.get_width()
        data = np.frombuffer(depth.get_data(), dtype=np.uint16).reshape(h, w).copy()
        # Orbbec reports depth scale in millimetres per unit -> metres
        try:
            self._depth_scale_m = float(depth.get_depth_scale()) / 1000.0
        except Exception:  # noqa: BLE001
            pass
        self._frame_id += 1
        return DepthFrame(
            timestamp_ms=timestamp_ms(),
            monotonic_ms=monotonic_ms(),
            frame_id=self._frame_id,
            width=w, height=h,
            depth_scale_m=self._depth_scale_m,
            data=data,
        )
