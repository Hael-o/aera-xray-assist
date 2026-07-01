"""UT-SCHEMA-001 — JSON schema validation: missing required fields caught
(verification-validation.md / api-schema.md §Schema Validation)."""

from __future__ import annotations

import jsonschema
import pytest

from xray_assist.common.messages import DepthSummary, RespirationState
from xray_assist.common.validation import is_valid, validate_message

DEV, SESS = "edge-001", "sess_test"


def _depth_msg() -> dict:
    return DepthSummary(
        device_id=DEV, session_id=SESS, frame_id=1,
        roi={"name": "chest_pa", "x": 200, "y": 140, "width": 240, "height": 200,
             "confidence": 0.9},
        measurement={"median_depth_mm": 882.0, "mean_depth_mm": 882.3,
                     "std_depth_mm": 0.5, "valid_pixel_ratio": 0.95,
                     "estimated_thickness_mm": 230.0},
        calibration={"profile_id": "p", "bed_origin_mm": 1112.7,
                     "extrinsic_version": "2026-06-24"},
        quality={"ir_saturation": False, "motion_artifact": False,
                 "clothing_artifact_score": 0.05, "confidence": 0.9},
    ).to_message()


def test_valid_message_passes():
    assert is_valid(_depth_msg()) is True
    validate_message(_depth_msg())  # must not raise


def test_missing_required_top_level_field_caught():
    msg = _depth_msg()
    del msg["frame_id"]            # required
    assert is_valid(msg) is False
    with pytest.raises(jsonschema.ValidationError):
        validate_message(msg)


def test_missing_required_measurement_field_caught():
    msg = _depth_msg()
    del msg["measurement"]["estimated_thickness_mm"]   # required nested field
    assert is_valid(msg) is False


def test_out_of_range_confidence_caught():
    msg = _depth_msg()
    msg["quality"]["confidence"] = 1.5   # schema bounds [0,1]
    assert is_valid(msg) is False


def test_unknown_message_type_rejected():
    with pytest.raises(jsonschema.ValidationError):
        validate_message({"type": "bogus.type"})


def test_respiration_state_message_valid():
    msg = RespirationState(
        device_id=DEV, session_id=SESS, state="stable_breath_hold",
        signal={"z_mm": 880.0, "dz_dt_mm_s": 0.1, "d2z_dt2_mm_s2": 0.0,
                "peak_phase": "plateau", "stable_duration_ms": 1200,
                "breathing_period_ms": None},
        gating={"window_open": True, "ready_to_capture": True, "abort": False,
                "reason": None},
        quality={"confidence": 0.9, "frame_drop_detected": False,
                 "motion_artifact": False},
    ).to_message()
    assert is_valid(msg) is True
