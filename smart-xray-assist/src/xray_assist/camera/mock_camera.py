"""Synthetic depth camera. Generates a flat bed plane plus a chest region whose
surface rises and falls with a configurable breathing waveform, so the whole
pipeline (depth -> gating -> recommendation) runs and is testable with no
hardware. Supports injectable events: breath-hold plateau and cough spike."""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..common.clock import monotonic_ms, timestamp_ms
from .interface import CameraConfig, DepthFrame, DeviceInfo, IDepthCamera

_DEPTH_SCALE_M = 0.001  # Z16 unit = 1 mm


class MockDepthCamera(IDepthCamera):
    def __init__(
        self,
        bed_depth_mm: float = 1112.7,
        chest_base_thickness_mm: float = 230.0,
        breathing_amplitude_mm: float = 8.0,
        breathing_period_ms: float = 4000.0,
        noise_mm: float = 0.5,
        seed: int = 1234,
    ) -> None:
        self._bed = bed_depth_mm
        self._chest = chest_base_thickness_mm
        self._amp = breathing_amplitude_mm
        self._period = breathing_period_ms
        self._noise = noise_mm
        self._rng = np.random.default_rng(seed)
        self._cfg: Optional[CameraConfig] = None
        self._frame_id = 0
        self._t0 = monotonic_ms()
        self._open = False
        # injectable scenario controls
        self.hold_breath = False          # freeze surface at plateau
        self._hold_offset_mm = 0.0
        self._held_surface_mm: Optional[float] = None  # frozen surface during hold
        self._last_surface_mm = chest_base_thickness_mm
        self._cough_frames = 0            # remaining frames of a cough spike

    # --- IDepthCamera ---------------------------------------------------------

    def open(self, cfg: CameraConfig) -> bool:
        self._cfg = cfg
        self._open = True
        self._t0 = monotonic_ms()
        return True

    def close(self) -> None:
        self._open = False

    def is_connected(self) -> bool:
        return self._open

    def usb_speed(self) -> str:
        return "super_speed"

    def get_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            vendor="mock", model=(self._cfg.model if self._cfg else "D455"),
            serial="mock-000000001", firmware="0.0.0", sdk_version="mock-1.0",
        )

    def get_frame(self, timeout_ms: int) -> Optional[DepthFrame]:
        if not self._open or self._cfg is None:
            return None
        w, h = self._cfg.width, self._cfg.height
        elapsed = monotonic_ms() - self._t0

        surface_mm = self._surface_thickness(elapsed)
        chest_depth_mm = self._bed - surface_mm  # closer to camera than bed

        # Build frame: bed plane everywhere, chest box in the centre.
        frame = np.full((h, w), self._bed, dtype=np.float64)
        cx0, cx1 = int(w * 0.30), int(w * 0.70)
        cy0, cy1 = int(h * 0.28), int(h * 0.72)
        frame[cy0:cy1, cx0:cx1] = chest_depth_mm

        # sensor noise
        frame += self._rng.normal(0.0, self._noise, size=frame.shape)

        # depth holes from gown/IR absorption (~5% invalid -> 0)
        holes = self._rng.random(frame.shape) < 0.05
        frame[holes] = 0.0

        z16 = np.clip(frame, 0, 65535).astype(np.uint16)
        self._frame_id += 1
        return DepthFrame(
            timestamp_ms=timestamp_ms(),
            monotonic_ms=monotonic_ms(),
            frame_id=self._frame_id,
            width=w, height=h,
            depth_scale_m=_DEPTH_SCALE_M,
            data=z16,
        )

    # --- scenario injection ---------------------------------------------------

    def trigger_cough(self, frames: int = 2) -> None:
        self._cough_frames = frames

    def _surface_thickness(self, elapsed_ms: float) -> float:
        if self._cough_frames > 0:
            self._cough_frames -= 1
            # sharp jerk: large momentary surface jump -> d2z/dt2 spike
            self._last_surface_mm = self._chest + self._amp + 30.0
            return self._last_surface_mm
        if self.hold_breath:
            # patient holds wherever they were: freeze at the last surface so the
            # cue->hold transition is smooth (a real breath-hold is not a step).
            if self._held_surface_mm is None:
                self._held_surface_mm = self._last_surface_mm + self._hold_offset_mm
            return self._held_surface_mm
        self._held_surface_mm = None
        phase = 2.0 * np.pi * (elapsed_ms % self._period) / self._period
        self._last_surface_mm = self._chest + self._amp * float(np.sin(phase))
        return self._last_surface_mm
