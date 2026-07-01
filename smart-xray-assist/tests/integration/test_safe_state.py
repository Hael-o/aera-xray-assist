"""IT-SAFE-001 — error event -> safe state: recommendations disabled within 2 s
(verification-validation.md / GTS-005).

Safe state never touches the X-ray machine's manual workflow; it only disables
this overlay's recommendations and flips the UI to Manual Mode."""

from __future__ import annotations

import time


def test_camera_disconnect_enters_safe_state_fast(orch):
    assert orch.safe_state is False

    # simulate the camera dropping off the USB bus
    orch.camera_service.camera.close()   # is_connected() -> False

    t0 = time.monotonic()
    orch.tick(20)                         # poll detects disconnect -> error -> safe state
    elapsed = time.monotonic() - t0

    assert orch.safe_state is True
    assert elapsed < 2.0, f"safe state took {elapsed:.2f}s (>2s)"
    assert orch.last_error is not None
    assert orch.last_error["code"] == "CAMERA_DISCONNECTED"
    assert orch.last_error["safe_state_entered"] is True


def test_recommendations_disabled_while_safe(orch):
    # a persistent fault (camera offline) keeps the system in safe state, so the
    # pipeline never advances and no new recommendation can be produced
    orch.camera_service.camera.close()
    before = orch.last_recommendation

    for _ in range(20):
        orch.tick(20)   # poll returns None (no frame) -> _on_frame never runs

    assert orch.safe_state is True
    assert orch.last_recommendation is before, "recommendation emitted while in safe state"


def test_safe_state_audited(orch):
    orch._enter_safe_state("CALIBRATION_DRIFT", "bed moved", module="depth_processor")
    assert orch.audit.verify_chain() is True
    snap = orch.state_snapshot()
    assert snap["safe_state"] is True
