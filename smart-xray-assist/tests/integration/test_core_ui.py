"""IT-CORE-UI-001 — api_gateway -> WebSocket: UI receives respiration state
within 200 ms (verification-validation.md / GTS-007)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from xray_assist.api.gateway import create_app


def _prime(orch, topic="respiration.state", max_frames=40):
    """Run the pipeline until the given topic has a latest message."""
    for _ in range(max_frames):
        orch.tick(20)
        if topic in orch.latest:
            return True
    return topic in orch.latest


def test_ws_replays_respiration_state_on_connect(orch):
    assert _prime(orch), "pipeline did not produce a respiration.state"
    app = create_app(orch)

    with TestClient(app) as client:
        t0 = time.monotonic()
        with client.websocket_connect("/ws/v1/events") as ws:
            seen = None
            # the gateway replays the latest of each topic on connect
            for _ in range(len(("depth.summary", "respiration.state",
                                "exposure.recommendation", "system.error")) + 1):
                msg = ws.receive_json()
                if msg.get("type") == "respiration.state":
                    seen = msg
                    break
            elapsed_ms = (time.monotonic() - t0) * 1000.0

    assert seen is not None, "UI never received respiration.state"
    assert seen["state"] in (
        "idle", "tracking", "cue_requested", "stable_breath_hold",
        "unstable", "abort", "timeout", "manual_mode")
    assert elapsed_ms < 200.0, f"respiration.state took {elapsed_ms:.0f}ms (>200ms)"


def test_rest_state_and_health(orch):
    app = create_app(orch)
    with TestClient(app) as client:
        h = client.get("/api/v1/health").json()
        assert h["device_id"] == orch.device_id
        assert h["status"] in ("ok", "degraded")
        s = client.get("/api/v1/state").json()
        assert s["session_id"] == orch.session_id
        assert "respiration_state" in s
