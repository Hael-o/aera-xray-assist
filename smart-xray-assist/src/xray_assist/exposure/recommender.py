"""exposure_recommender: LUT lookup + guardrail clamp + operator-approval gate.

Recommendation values are REFERENCE-ONLY. operator_approval_required is always
true; nothing happens downstream until the operator approves (api-schema.md).

LUT rows flagged "pending clinical review" (pediatric/bariatric in the MVP LUT)
return manual_review_required=true and NO numeric suggestion — the UI shows no
kVp/mAs for those modes (deployment.md)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ..common.config import load_yaml, require_valid_config
from ..common.messages import ExposureRecommendation

_REFERENCE_MSG = "Reference values — operator confirmation required before use."
_MANUAL_MSG = "Manual review required — no automatic suggestion for this mode."


@dataclass
class Guardrails:
    kvp_min: float
    kvp_max: float
    mas_min: float
    mas_max: float


class ExposureRecommender:
    def __init__(self, lut: dict[str, Any], device_id: str, session_id: str) -> None:
        require_valid_config(lut, ("metadata", "guardrails"), "exposure_lut.yaml")
        self.lut = lut
        self.device_id = device_id
        self.session_id = session_id
        self.version = lut["metadata"].get("version", "0.0.0")
        g = lut["guardrails"]
        self.guard = Guardrails(
            kvp_min=float(g["kvp_min"]), kvp_max=float(g["kvp_max"]),
            mas_min=float(g["mas_min"]), mas_max=float(g["mas_max"]),
        )
        self.lut_hash = "sha256:" + hashlib.sha256(
            json.dumps(lut, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @classmethod
    def from_file(cls, path: str | Path, device_id: str, session_id: str) -> "ExposureRecommender":
        return cls(load_yaml(path), device_id, session_id)

    def recommend(self, thickness_mm: float, body_region: str = "chest_pa",
                  patient_mode: str = "adult",
                  input_confidence: float = 0.9) -> ExposureRecommendation:
        row = self._lookup(thickness_mm, body_region, patient_mode)
        inp = {
            "estimated_thickness_mm": round(thickness_mm, 1),
            "body_region": body_region,
            "patient_mode": patient_mode,
            "confidence": round(input_confidence, 3),
        }

        # pending clinical review OR no matching row -> manual review, no numbers
        if row is None or row.get("note") == "pending clinical review":
            manual = True
            rec = {
                "kvp": None, "mas": None,
                "source": f"lut_v{self.version}", "model_hash": self.lut_hash,
                "confidence": 0.0, "operator_approval_required": True,
            }
            guardrails = {
                "within_min_max": False,
                "pediatric_limit_applied": patient_mode == "pediatric",
                "bariatric_offset_applied": patient_mode == "bariatric",
                "manual_review_required": True,
            }
            display = {"message": _MANUAL_MSG, "severity": "warning"}
            return ExposureRecommendation(self.device_id, self.session_id, inp,
                                          rec, guardrails, display)

        kvp_raw, mas_raw = float(row["kvp"]), float(row["mas"])
        kvp, kvp_clamped = self._clamp(kvp_raw, self.guard.kvp_min, self.guard.kvp_max)
        mas, mas_clamped = self._clamp(mas_raw, self.guard.mas_min, self.guard.mas_max)
        within = not (kvp_clamped or mas_clamped)

        rec = {
            "kvp": kvp, "mas": mas,
            "source": f"lut_v{self.version}", "model_hash": self.lut_hash,
            "confidence": round(min(input_confidence, 0.9), 3),
            "operator_approval_required": True,    # always — never auto-fire
        }
        guardrails = {
            "within_min_max": within,
            "pediatric_limit_applied": patient_mode == "pediatric",
            "bariatric_offset_applied": patient_mode == "bariatric",
            "manual_review_required": False,
        }
        display = {
            "message": _REFERENCE_MSG if within
            else _REFERENCE_MSG + " (value clamped to safe range)",
            "severity": "info" if within else "warning",
        }
        return ExposureRecommendation(self.device_id, self.session_id, inp,
                                      rec, guardrails, display)

    # --- internals ------------------------------------------------------------

    def _lookup(self, thickness_mm: float, body_region: str,
                patient_mode: str) -> Optional[dict]:
        region = self.lut.get(body_region)
        if not isinstance(region, dict):
            return None
        rows = region.get(patient_mode)
        if not rows:
            return None
        for row in rows:
            if row["thickness_mm_min"] <= thickness_mm <= row["thickness_mm_max"]:
                return row
        return None

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> tuple[float, bool]:
        clamped = min(max(value, lo), hi)
        return clamped, (clamped != value)
