"""Vendor-agnostic depth camera interface (camera.md IDepthCamera).

Upper services (depth_processor, etc.) never see vendor SDK types. Switching
cameras in production is a config change (camera.yaml provider), not a code
change. Python mirror of the C++ IDepthCamera in the design docs."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class DepthFrame:
    timestamp_ms: int           # wall clock
    monotonic_ms: int           # latency/ordering
    frame_id: int
    width: int
    height: int
    depth_scale_m: float        # meters per raw unit (Z16 -> meters)
    data: np.ndarray            # uint16 HxW, owned by caller for the MVP


@dataclass
class DeviceInfo:
    vendor: str
    model: str
    serial: str
    firmware: str = "unknown"
    sdk_version: str = "unknown"


@dataclass
class CameraConfig:
    provider: str
    model: str = "D455"
    serial: str = "auto"
    width: int = 640
    height: int = 480
    fps: int = 30
    align_depth_to_color: bool = False
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, camera_section: dict) -> "CameraConfig":
        c = dict(camera_section)
        return cls(
            provider=c.get("provider", "mock"),
            model=c.get("model", "D455"),
            serial=str(c.get("serial", "auto")),
            width=int(c.get("width", 640)),
            height=int(c.get("height", 480)),
            fps=int(c.get("fps", 30)),
            align_depth_to_color=bool(c.get("align_depth_to_color", False)),
        )


class IDepthCamera(abc.ABC):
    @abc.abstractmethod
    def open(self, cfg: CameraConfig) -> bool: ...

    @abc.abstractmethod
    def close(self) -> None: ...

    @abc.abstractmethod
    def get_frame(self, timeout_ms: int) -> Optional[DepthFrame]:
        """Return next frame or None on timeout."""

    @abc.abstractmethod
    def get_device_info(self) -> DeviceInfo: ...

    @abc.abstractmethod
    def is_connected(self) -> bool: ...

    @abc.abstractmethod
    def usb_speed(self) -> str:
        """e.g. 'super_speed' / 'high_speed'. camera.md: silent USB 2.0 fallback
        must be detectable at startup."""
