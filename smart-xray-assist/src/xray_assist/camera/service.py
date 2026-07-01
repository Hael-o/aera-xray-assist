"""camera_service: owns the camera, pulls frames, publishes CameraFrameMeta on
the event bus and hands the raw frame to the depth processor. Detects USB 2.0
fallback and frame-drop spikes -> safe state (camera.md fault handling)."""

from __future__ import annotations

from typing import Callable, Optional

from ..common.clock import monotonic_ms
from ..common.errors import ErrorEvent
from ..common.event_bus import EventBus
from ..common.messages import make_camera_frame_meta
from .interface import CameraConfig, DepthFrame, IDepthCamera
from .mock_camera import MockDepthCamera


def build_camera(cfg: CameraConfig) -> IDepthCamera:
    """Factory: provider string -> adapter. Switching cameras is config-only."""
    provider = cfg.provider.lower()
    if provider == "mock":
        return MockDepthCamera()
    if provider == "realsense":
        from .realsense_adapter import RealSenseCamera
        return RealSenseCamera()
    if provider == "orbbec":
        from .orbbec_adapter import OrbbecCamera
        return OrbbecCamera()
    raise ValueError(f"unsupported camera provider: {cfg.provider!r}")


class CameraService:
    def __init__(self, cfg: CameraConfig, bus: EventBus, device_id: str,
                 session_id: str, quality_cfg: dict,
                 camera: Optional[IDepthCamera] = None) -> None:
        self.cfg = cfg
        self.bus = bus
        self.device_id = device_id
        self.session_id = session_id
        self.quality_cfg = quality_cfg
        self.camera = camera or build_camera(cfg)
        self._dropped_frames = 0
        self._drop_window_start = monotonic_ms()
        self._drops_this_min = 0
        # frame callback (depth_processor.ingest) — set by orchestrator
        self.on_frame: Optional[Callable[[DepthFrame], None]] = None
        self.on_error: Optional[Callable[[dict], None]] = None

    def start(self) -> None:
        if not self.camera.open(self.cfg):
            self._emit_error("CAMERA_DISCONNECTED", "camera failed to open")
            return
        speed = self.camera.usb_speed()
        if speed not in ("super_speed", "unknown") and "super" not in speed.lower():
            # camera.md: USB 2.0 fallback -> reduced-capability warning, not fatal
            self._emit_error("FRAME_DROP_EXCEEDED",
                             f"USB link negotiated as {speed} (expected super_speed)",
                             severity="warning")

    def stop(self) -> None:
        self.camera.close()

    def poll_once(self, timeout_ms: int = 100) -> Optional[DepthFrame]:
        if not self.camera.is_connected():
            self._emit_error("CAMERA_DISCONNECTED", "camera disconnected")
            return None
        frame = self.camera.get_frame(timeout_ms)
        if frame is None:
            self._register_drop()
            return None
        info = self.camera.get_device_info()
        meta = make_camera_frame_meta(
            self.device_id, self.session_id, frame.frame_id,
            camera={"vendor": info.vendor, "model": info.model,
                    "serial": info.serial, "firmware": info.firmware,
                    "sdk": info.sdk_version},
            stream={"depth_width": frame.width, "depth_height": frame.height,
                    "depth_fps": self.cfg.fps, "format": "z16",
                    "depth_scale_m": frame.depth_scale_m},
            shared_memory={"name": "/xray_depth_ring_0", "slot_index": 0,
                           "bytes": int(frame.data.nbytes)},
            quality={"dropped_frames": self._dropped_frames,
                     "usb_speed": self.camera.usb_speed(),
                     "temperature_c": None, "confidence": 0.98},
        )
        self.bus.publish("camera.frame_meta", meta)
        if self.on_frame is not None:
            self.on_frame(frame)
        return frame

    def _register_drop(self) -> None:
        self._dropped_frames += 1
        self._drops_this_min += 1
        now = monotonic_ms()
        if now - self._drop_window_start >= 60_000:
            self._drop_window_start = now
            self._drops_this_min = 0
        max_drop = int(self.quality_cfg.get("max_frame_drop_per_min", 30))
        if self._drops_this_min > max_drop:
            self._emit_error("FRAME_DROP_EXCEEDED",
                             f"frame drops {self._drops_this_min}/min exceed {max_drop}")

    def _emit_error(self, code: str, message: str, severity: str = "error") -> None:
        evt = ErrorEvent(device_id=self.device_id, session_id=self.session_id,
                         code=code, message=message, module="camera_service",
                         severity=severity).to_message()
        self.bus.publish("system.error", evt)
        if self.on_error is not None:
            self.on_error(evt)
