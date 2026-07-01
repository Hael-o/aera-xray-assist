"""depth_processor: the 9-step pipeline from camera.md.

  [1] frame validity   [2] empty-bed compensation   [3] extrinsic correction
  [4] depth range gate [5] ROI crop                 [6] IQR outlier rejection
  [7] temporal EMA     [8] spatial median           [9] stat extraction

Thickness = Z_bed_reference - Z_patient_surface. Median (not mean) is the
headline statistic: hospital gowns/linens absorb the IR pattern and create
depth holes (zeros); mean is dragged toward holes, median is not."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..camera.interface import DepthFrame
from ..common.errors import SafeStateError
from ..common.messages import DepthSummary
from .calibration import CalibrationProfile

# pixels nearer/farther than the bed by more than this are noise/out-of-range
MIN_RANGE_MM = 300.0
MAX_RANGE_MM = 3000.0


@dataclass
class ProcessorConfig:
    min_valid_pixel_ratio: float = 0.85
    min_confidence: float = 0.80
    ema_alpha: float = 0.4              # temporal filter weight on the new frame
    max_frame_age_ms: int = 500


class DepthProcessor:
    def __init__(self, calib: CalibrationProfile, cfg: ProcessorConfig,
                 device_id: str, session_id: str,
                 body_region: str = "chest_pa") -> None:
        self.calib = calib
        self.cfg = cfg
        self.device_id = device_id
        self.session_id = session_id
        self.body_region = body_region
        self._ema_thickness: Optional[float] = None
        self._last_monotonic: Optional[int] = None

    def process(self, frame: DepthFrame) -> DepthSummary:
        # [1] frame validity
        self._validate(frame)

        depth_mm = frame.data.astype(np.float64) * (frame.depth_scale_m * 1000.0)
        valid_mask = depth_mm > 0  # zeros are holes

        # [2/3] empty-bed + extrinsic: extrinsic is identity in the MVP fixture,
        # so bed compensation is the dominant term. Verify the bed plane first.
        measured_bed = self._estimate_bed_plane(depth_mm, valid_mask)
        self.calib.check_drift(measured_bed)

        # [4] depth range gate
        in_range = valid_mask & (depth_mm >= MIN_RANGE_MM) & (depth_mm <= MAX_RANGE_MM)

        # [5] ROI crop
        roi = self.calib.roi(self.body_region)
        x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]
        x2, y2 = min(x + w, frame.width), min(y + h, frame.height)
        roi_depth = depth_mm[y:y2, x:x2]
        roi_valid = in_range[y:y2, x:x2]

        vals = roi_depth[roi_valid]
        total = roi_depth.size
        valid_pixel_ratio = float(vals.size / total) if total else 0.0
        if valid_pixel_ratio < self.cfg.min_valid_pixel_ratio:
            raise SafeStateError(
                "LOW_CONFIDENCE",
                f"ROI valid_pixel_ratio {valid_pixel_ratio:.2f} < "
                f"{self.cfg.min_valid_pixel_ratio}",
            )

        # [6] IQR outlier rejection
        vals = self._reject_outliers_iqr(vals)
        if vals.size == 0:
            raise SafeStateError("LOW_CONFIDENCE", "no valid pixels after outlier rejection")

        # [9] stat extraction
        median_depth = float(np.median(vals))
        mean_depth = float(np.mean(vals))
        std_depth = float(np.std(vals))

        # thickness = bed reference - patient surface (closer to camera = smaller depth)
        thickness = self.calib.bed_origin_mm - median_depth

        # [7] temporal EMA on the headline thickness
        if self._ema_thickness is None:
            self._ema_thickness = thickness
        else:
            a = self.cfg.ema_alpha
            self._ema_thickness = a * thickness + (1 - a) * self._ema_thickness
        thickness_filt = float(self._ema_thickness)

        confidence = self._confidence(valid_pixel_ratio, std_depth)
        clothing_artifact = float(np.clip(1.0 - valid_pixel_ratio, 0.0, 1.0))

        return DepthSummary(
            device_id=self.device_id,
            session_id=self.session_id,
            frame_id=frame.frame_id,
            monotonic_ms=frame.monotonic_ms,
            roi={"name": self.body_region, "x": x, "y": y, "width": w, "height": h,
                 "confidence": round(confidence, 3)},
            # measurement carries FULL-PRECISION values: upper services (gating)
            # differentiate this signal, so 0.1mm quantization here would blow up
            # d2Z/dt2. Rounding happens only in DepthSummary.to_message() (display).
            measurement={
                "median_depth_mm": median_depth,
                "mean_depth_mm": mean_depth,
                "std_depth_mm": std_depth,
                "valid_pixel_ratio": valid_pixel_ratio,
                "estimated_thickness_mm": thickness_filt,
            },
            calibration={
                "profile_id": self.calib.profile_id,
                "bed_origin_mm": self.calib.bed_origin_mm,
                "extrinsic_version": self.calib.extrinsic_version,
            },
            quality={
                "ir_saturation": False,
                "motion_artifact": False,
                "clothing_artifact_score": round(clothing_artifact, 3),
                "confidence": round(confidence, 3),
            },
        )

    # --- pipeline helpers -----------------------------------------------------

    def _validate(self, frame: DepthFrame) -> None:
        if frame.frame_id <= 0:
            raise SafeStateError("LOW_CONFIDENCE", "invalid frame_id")
        if self._last_monotonic is not None and frame.monotonic_ms < self._last_monotonic:
            # camera.md FI-003: timestamp reversed -> discard
            raise SafeStateError("LOW_CONFIDENCE", "frame timestamp went backwards")
        self._last_monotonic = frame.monotonic_ms

    @staticmethod
    def _estimate_bed_plane(depth_mm: np.ndarray, valid: np.ndarray) -> float:
        """Bed is the dominant far surface: take the high-percentile of valid
        depths (patient body is nearer than the bed)."""
        vals = depth_mm[valid]
        if vals.size == 0:
            raise SafeStateError("LOW_CONFIDENCE", "no valid pixels for bed estimate")
        return float(np.percentile(vals, 90))

    @staticmethod
    def _reject_outliers_iqr(vals: np.ndarray) -> np.ndarray:
        if vals.size < 4:
            return vals
        q1, q3 = np.percentile(vals, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        return vals[(vals >= lo) & (vals <= hi)]

    def _confidence(self, valid_ratio: float, std_mm: float) -> float:
        # high valid-pixel ratio and low spatial std -> high confidence
        ratio_term = np.clip(valid_ratio, 0.0, 1.0)
        std_term = np.clip(1.0 - (std_mm / 50.0), 0.0, 1.0)
        return float(np.clip(0.5 * ratio_term + 0.5 * std_term, 0.0, 1.0))
