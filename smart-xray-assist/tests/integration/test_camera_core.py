"""IT-CAM-CORE-001 — camera_service -> depth_processor: frame_meta received and
parsed correctly (verification-validation.md)."""

from __future__ import annotations

from xray_assist.common.validation import is_valid


def test_frame_meta_published_and_valid(orch):
    received = []
    orch.bus.subscribe("camera.frame_meta", lambda m: received.append(m))

    frame = orch.camera_service.poll_once(timeout_ms=50)
    assert frame is not None

    assert received, "no camera.frame_meta published"
    meta = received[-1]
    assert meta["type"] == "camera.frame_meta"
    assert is_valid(meta), "frame_meta failed schema validation"
    # parsed fields the depth processor depends on
    assert meta["stream"]["format"] == "z16"
    assert meta["stream"]["depth_width"] == frame.width
    assert meta["frame_id"] == frame.frame_id


def test_frame_flows_through_to_depth_summary(orch):
    depth = []
    orch.bus.subscribe("depth.summary", lambda m: depth.append(m))

    orch.tick(50)

    assert depth, "no depth.summary produced from frame"
    summary = depth[-1]
    assert is_valid(summary)
    assert summary["measurement"]["estimated_thickness_mm"] > 0
    # the mock chest is ~230mm thick
    assert 150 < summary["measurement"]["estimated_thickness_mm"] < 320
