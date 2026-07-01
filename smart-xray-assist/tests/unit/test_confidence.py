"""UT-CONF-001 — All `confidence` fields: values in [0.0, 1.0], definitions
consistent (verification-validation.md). Recursively walks every message the
pipeline emits and asserts each "confidence" value is a valid probability."""

from __future__ import annotations

import math
from pathlib import Path

from xray_assist.exposure.recommender import ExposureRecommender

_ROOT = Path(__file__).resolve().parents[2]


def _confidences(obj, path="$"):
    """Yield (path, value) for every "confidence" key anywhere in the structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "confidence":
                yield (f"{path}.{k}", v)
            yield from _confidences(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _confidences(v, f"{path}[{i}]")


def _assert_all_valid(msg):
    found = list(_confidences(msg))
    assert found, "message has no confidence field to check"
    for p, v in found:
        assert v is not None, f"{p} is None"
        assert isinstance(v, (int, float)) and not isinstance(v, bool), f"{p} not numeric: {v!r}"
        assert not math.isnan(v), f"{p} is NaN"
        assert 0.0 <= v <= 1.0, f"{p} out of [0,1]: {v}"


def test_recommendation_confidences_in_range():
    rec = ExposureRecommender.from_file(_ROOT / "configs" / "exposure_lut.yaml",
                                        "edge-001", "sess_test")
    for thickness in (50, 230, 300, 500):
        for conf in (0.0, 0.5, 0.9, 1.0):
            msg = rec.recommend(thickness, "chest_pa", "adult",
                                input_confidence=conf).to_message()
            _assert_all_valid(msg)


def test_manual_review_confidence_is_zero_not_negative():
    rec = ExposureRecommender.from_file(_ROOT / "configs" / "exposure_lut.yaml",
                                        "edge-001", "sess_test")
    msg = rec.recommend(100, "chest_pa", "pediatric").to_message()
    assert msg["recommendation"]["confidence"] == 0.0


def test_pipeline_messages_confidences_in_range(orch):
    """Drive the full mock pipeline and check depth/respiration/recommendation."""
    import time
    cam = orch.camera_service.camera
    # drive at the configured ~30fps cadence (the gating EMA/threshold are tuned
    # for camera.yaml fps; run_mvp likewise sleeps 1/fps)
    for i in range(160):
        if i == 30:
            cam.hold_breath = True   # trigger a breath-hold -> recommendation
        orch.tick(5)
        time.sleep(0.033)
        if orch.latest.get("exposure.recommendation") is not None:
            break
    for topic in ("depth.summary", "respiration.state", "exposure.recommendation"):
        msg = orch.latest.get(topic)
        if msg is not None:
            _assert_all_valid(msg)
    # the breath-hold path must have produced a recommendation to check
    assert orch.latest.get("exposure.recommendation") is not None
