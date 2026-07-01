"""respiration_gating: breathing waveform analysis + state machine (camera.md).

Signals:
  dZ/dt   = (Z[t]-Z[t-1]) / dt_ms          velocity
  d2Z/dt2 = (dZ/dt[t]-dZ/dt[t-1]) / dt_ms  acceleration (cough/jerk detection)

A cough produces a spike in d2Z/dt2 distinct from a slow breath. The d2Z/dt2
channel triggers `abort` even if dZ/dt has not crossed the velocity threshold.

State machine:
  idle -> tracking -> cue_requested -> stable_breath_hold -> idle
  tracking --elapsed>T_timeout--> timeout
  any --cough/camera_error/low_confidence--> abort
  any --manual_override--> manual_mode

Stable requires ALL of:
  abs(dZ/dt) < theta_v AND var(Z[t-w:t]) < theta_var
  AND valid_pixel_ratio > theta_quality AND stable_duration > T_min
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from ..common.clock import monotonic_ms
from ..common.messages import RespirationState


@dataclass
class GatingConfig:
    stable_dz_dt_threshold_mm_s: float = 2.0
    stable_variance_threshold: float = 0.03
    min_stable_duration_ms: int = 1000
    timeout_ms: int = 10000
    cough_abort_d2z_threshold_mm_s2: float = 25.0
    min_valid_pixel_ratio: float = 0.85
    variance_window: int = 15
    # camera.md step-7 temporal filter: EMA on z and dz/dt suppresses the
    # residual sensor noise that the 2nd derivative would otherwise amplify.
    ema_alpha_z: float = 0.3
    ema_alpha_dz: float = 0.3
    # derivative channel is invalid until the EMA filters converge; suppress the
    # cough abort for the first N frames (~0.3s @30fps) to avoid a startup spike.
    warmup_frames: int = 8
    # frames are sampled at a near-fixed cadence, so dividing finite differences
    # by the raw per-frame timestamp delta injects acquisition jitter (±25%)
    # straight into d2Z/dt2. EMA-smooth the sample interval to track the true
    # cadence (33ms, 50ms, ...) without the per-frame jitter.
    ema_alpha_dt: float = 0.2

    @classmethod
    def from_yaml(cls, gating_section: dict) -> "GatingConfig":
        g = dict(gating_section)
        return cls(
            stable_dz_dt_threshold_mm_s=float(g.get("stable_dz_dt_threshold_mm_s", 2.0)),
            stable_variance_threshold=float(g.get("stable_variance_threshold", 0.03)),
            min_stable_duration_ms=int(g.get("min_stable_duration_ms", 1000)),
            timeout_ms=int(g.get("timeout_ms", 10000)),
            cough_abort_d2z_threshold_mm_s2=float(g.get("cough_abort_d2z_threshold_mm_s2", 25.0)),
            min_valid_pixel_ratio=float(g.get("min_valid_pixel_ratio", 0.85)),
            variance_window=int(g.get("variance_window", 15)),
            ema_alpha_z=float(g.get("ema_alpha_z", 0.3)),
            ema_alpha_dz=float(g.get("ema_alpha_dz", 0.3)),
            warmup_frames=int(g.get("warmup_frames", 8)),
            ema_alpha_dt=float(g.get("ema_alpha_dt", 0.2)),
        )


class RespirationGating:
    def __init__(self, cfg: GatingConfig, device_id: str, session_id: str) -> None:
        self.cfg = cfg
        self.device_id = device_id
        self.session_id = session_id
        self.state = "idle"
        self._z_window: deque[float] = deque(maxlen=cfg.variance_window)
        self._ema_z: Optional[float] = None
        self._ema_dz: Optional[float] = None
        self._ema_dt: Optional[float] = None
        self._samples = 0
        self._prev_z: Optional[float] = None
        self._prev_dz_dt: Optional[float] = None
        self._prev_t: Optional[int] = None
        self._stable_since: Optional[int] = None
        self._tracking_since: Optional[int] = None
        self._last = {"z": 0.0, "dz_dt": 0.0, "d2z_dt2": 0.0, "period_ms": None}

    # --- lifecycle ------------------------------------------------------------

    def start_tracking(self) -> None:
        self.state = "tracking"
        self._tracking_since = monotonic_ms()
        self._stable_since = None

    def request_cue(self) -> None:
        if self.state in ("tracking", "cue_requested"):
            self.state = "cue_requested"

    def manual_override(self) -> None:
        self.state = "manual_mode"

    def reset(self) -> None:
        self.state = "idle"
        self._z_window.clear()
        self._ema_z = self._ema_dz = self._ema_dt = None
        self._samples = 0
        self._prev_z = self._prev_dz_dt = self._prev_t = None
        self._stable_since = self._tracking_since = None

    # --- per-summary update ---------------------------------------------------

    def update(self, z_mm: float, valid_pixel_ratio: float,
               now_ms: Optional[int] = None) -> RespirationState:
        now = now_ms if now_ms is not None else monotonic_ms()
        # [step-7] EMA-smooth the surface signal before differentiating
        if self._ema_z is None:
            self._ema_z = z_mm
        else:
            a = self.cfg.ema_alpha_z
            self._ema_z = a * z_mm + (1 - a) * self._ema_z
        z_s = float(self._ema_z)
        dz_dt, d2z_dt2 = self._derivatives(z_s, now)
        self._samples += 1
        self._z_window.append(z_s)
        self._last = {"z": z_s, "dz_dt": dz_dt, "d2z_dt2": d2z_dt2,
                      "period_ms": self._last["period_ms"]}

        if self.state == "manual_mode":
            return self._emit("manual_mode", dz_dt, d2z_dt2, z_mm, abort=False,
                              reason="operator manual override")

        # cough / jerk abort takes priority in any active state (once the EMA
        # filters have converged — see warmup_frames)
        if (self._samples > self.cfg.warmup_frames
                and self.state in ("tracking", "cue_requested", "stable_breath_hold")):
            if abs(d2z_dt2) > self.cfg.cough_abort_d2z_threshold_mm_s2:
                self.state = "abort"
                return self._emit("abort", dz_dt, d2z_dt2, z_mm, abort=True,
                                  reason="cough/motion spike (d2z/dt2)")

        if self.state == "idle":
            return self._emit("idle", dz_dt, d2z_dt2, z_mm)

        # timeout from tracking/cue without reaching stable
        if (self.state in ("tracking", "cue_requested")
                and self._tracking_since is not None
                and now - self._tracking_since > self.cfg.timeout_ms):
            self.state = "timeout"
            return self._emit("timeout", dz_dt, d2z_dt2, z_mm, reason="stable window not reached")

        stable_now = self._is_stable(dz_dt, valid_pixel_ratio)

        if self.state in ("tracking", "cue_requested"):
            if stable_now:
                if self._stable_since is None:
                    self._stable_since = now
                dur = now - self._stable_since
                if dur >= self.cfg.min_stable_duration_ms:
                    self.state = "stable_breath_hold"
                    return self._emit("stable_breath_hold", dz_dt, d2z_dt2, z_mm,
                                      window_open=True, ready=True,
                                      stable_duration_ms=dur)
                # building stability but not long enough yet
                return self._emit(self.state, dz_dt, d2z_dt2, z_mm,
                                  stable_duration_ms=dur)
            self._stable_since = None
            return self._emit(self.state, dz_dt, d2z_dt2, z_mm)

        if self.state == "stable_breath_hold":
            if not stable_now:
                self.state = "unstable"
                self._stable_since = None
                return self._emit("unstable", dz_dt, d2z_dt2, z_mm,
                                  reason="motion above threshold")
            dur = now - (self._stable_since or now)
            return self._emit("stable_breath_hold", dz_dt, d2z_dt2, z_mm,
                              window_open=True, ready=True, stable_duration_ms=dur)

        if self.state == "unstable":
            # recover back to tracking when motion settles
            self.state = "tracking"
            return self._emit("tracking", dz_dt, d2z_dt2, z_mm)

        return self._emit(self.state, dz_dt, d2z_dt2, z_mm)

    # --- internals ------------------------------------------------------------

    def _derivatives(self, z_mm: float, now: int) -> tuple[float, float]:
        if self._prev_z is None or self._prev_t is None:
            self._prev_z, self._prev_t = z_mm, now
            return 0.0, 0.0
        measured = max(now - self._prev_t, 1)
        if self._ema_dt is None:
            self._ema_dt = float(measured)
        else:
            a = self.cfg.ema_alpha_dt
            self._ema_dt = a * measured + (1 - a) * self._ema_dt
        dt_ms = self._ema_dt
        dz_raw = (z_mm - self._prev_z) / dt_ms * 1000.0         # mm/s
        # EMA-smooth velocity too: a single noisy dz sample otherwise produces a
        # spurious acceleration spike that trips the cough abort.
        if self._ema_dz is None:
            dz_dt = dz_raw
        else:
            a = self.cfg.ema_alpha_dz
            dz_dt = a * dz_raw + (1 - a) * self._ema_dz
        self._ema_dz = dz_dt
        d2z_dt2 = 0.0
        if self._prev_dz_dt is not None:
            d2z_dt2 = (dz_dt - self._prev_dz_dt) / dt_ms * 1000.0  # mm/s^2
        self._prev_z, self._prev_t, self._prev_dz_dt = z_mm, now, dz_dt
        return dz_dt, d2z_dt2

    def _is_stable(self, dz_dt: float, valid_pixel_ratio: float) -> bool:
        if abs(dz_dt) >= self.cfg.stable_dz_dt_threshold_mm_s:
            return False
        if valid_pixel_ratio <= self.cfg.min_valid_pixel_ratio:
            return False
        if len(self._z_window) >= 2:
            import statistics
            if statistics.pvariance(self._z_window) >= self.cfg.stable_variance_threshold:
                return False
        return True

    def _emit(self, state: str, dz_dt: float, d2z_dt2: float, z_mm: float,
              window_open: bool = False, ready: bool = False, abort: bool = False,
              reason: Optional[str] = None,
              stable_duration_ms: float = 0.0) -> RespirationState:
        return RespirationState(
            device_id=self.device_id,
            session_id=self.session_id,
            state=state,
            signal={
                "z_mm": round(z_mm, 1),
                "dz_dt_mm_s": round(dz_dt, 2),
                "d2z_dt2_mm_s2": round(d2z_dt2, 3),
                "peak_phase": "plateau" if state == "stable_breath_hold" else None,
                "stable_duration_ms": round(stable_duration_ms, 0),
                "breathing_period_ms": self._last["period_ms"],
            },
            gating={
                "window_open": window_open,
                "ready_to_capture": ready,
                "abort": abort,
                "reason": reason,
            },
            quality={
                "confidence": 0.9 if state == "stable_breath_hold" else 0.8,
                "frame_drop_detected": False,
                "motion_artifact": state in ("unstable", "abort"),
            },
        )
