"""Calibration profile load + signature gate + empty-bed drift check (camera.md).

A profile is signed; an unsigned/mismatched file blocks the service from
starting (CALIBRATION_MISSING). At runtime, if the empty-bed plane drifts
beyond tolerance (camera bumped, table moved) the processor refuses to publish
recommendations and logs CALIBRATION_DRIFT."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common.config import verify_signature
from ..common.errors import SafeStateError

# Empty-bed plane may drift this much (mm) before CALIBRATION_DRIFT.
DEFAULT_DRIFT_TOLERANCE_MM = 15.0


@dataclass
class CalibrationProfile:
    profile_id: str
    bed_origin_mm: float
    extrinsic_matrix_4x4: list[list[float]]
    roi_templates: dict[str, dict[str, int]]
    valid_pixel_ratio_baseline: float
    camera_serial: str
    extrinsic_version: str
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationProfile":
        p = Path(path)
        if not p.exists():
            raise SafeStateError("CALIBRATION_MISSING", f"calibration not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        signature = data.get("signature", "")
        # signature covers the profile without the signature field itself
        payload = json.dumps({k: v for k, v in data.items() if k != "signature"},
                             sort_keys=True, separators=(",", ":")).encode()
        if not verify_signature(payload, signature):
            raise SafeStateError("CALIBRATION_MISSING",
                                 f"calibration signature invalid: {p}")
        try:
            return cls(
                profile_id=data["profile_id"],
                bed_origin_mm=float(data["bed_origin_mm"]),
                extrinsic_matrix_4x4=data["extrinsic_matrix_4x4"],
                roi_templates=data["roi_templates"],
                valid_pixel_ratio_baseline=float(data.get("valid_pixel_ratio_baseline", 0.9)),
                camera_serial=str(data.get("camera_serial", "")),
                extrinsic_version=str(data.get("created_at", "unknown"))[:10],
                raw=data,
            )
        except KeyError as exc:
            raise SafeStateError("CALIBRATION_MISSING",
                                 f"calibration missing field {exc}") from exc

    def roi(self, body_region: str) -> dict[str, int]:
        tpl = self.roi_templates.get(body_region)
        if tpl is None:
            raise SafeStateError("ROI_NOT_FOUND",
                                 f"no ROI template for {body_region!r}")
        return tpl

    def check_drift(self, measured_bed_mm: float,
                    tolerance_mm: float = DEFAULT_DRIFT_TOLERANCE_MM) -> None:
        if abs(measured_bed_mm - self.bed_origin_mm) > tolerance_mm:
            raise SafeStateError(
                "CALIBRATION_DRIFT",
                f"empty-bed plane drifted {measured_bed_mm:.1f}mm vs "
                f"reference {self.bed_origin_mm:.1f}mm (tol {tolerance_mm}mm)",
            )
