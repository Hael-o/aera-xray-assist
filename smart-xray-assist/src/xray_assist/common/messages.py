"""Message contracts (api-schema.md). Upper services depend ONLY on these types,
never on vendor SDK types. All factories stamp schema_version + common fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .. import SCHEMA_VERSION
from .clock import monotonic_ms, timestamp_ms

# ---- enums (as string constants; validated by JSON Schema) -------------------

RESPIRATION_STATES = (
    "idle", "tracking", "cue_requested", "stable_breath_hold",
    "unstable", "abort", "timeout", "manual_mode",
)

BODY_REGIONS = ("chest_pa", "chest_lateral", "abdomen_ap", "pelvis_ap")
PATIENT_MODES = ("adult", "pediatric", "bariatric")

OPERATOR_ACTIONS = (
    "start_session", "calibrate_empty_bed", "play_breath_cue",
    "approve_recommendation", "reject_recommendation",
    "switch_manual_mode", "abort", "end_session", "trigger_cough",
)


def _common(device_id: str, session_id: Optional[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "device_id": device_id,
        "session_id": session_id,
        "timestamp_ms": timestamp_ms(),
        "monotonic_ms": monotonic_ms(),
    }


# ---- typed payloads ----------------------------------------------------------

@dataclass
class DepthSummary:
    device_id: str
    session_id: str
    frame_id: int
    roi: dict[str, Any]
    measurement: dict[str, Any]
    calibration: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    monotonic_ms: Optional[int] = None  # frame capture time; drives gating dt

    # display rounding (gating consumes the raw `measurement` dict directly)
    _DISPLAY_ROUND = {
        "median_depth_mm": 1, "mean_depth_mm": 1, "std_depth_mm": 2,
        "valid_pixel_ratio": 3, "estimated_thickness_mm": 1,
    }

    def display_measurement(self) -> dict[str, Any]:
        out = dict(self.measurement)
        for k, nd in self._DISPLAY_ROUND.items():
            if k in out and out[k] is not None:
                out[k] = round(float(out[k]), nd)
        return out

    def to_message(self) -> dict[str, Any]:
        msg = _common(self.device_id, self.session_id)
        msg.update({
            "type": "depth.summary",
            "frame_id": self.frame_id,
            "roi": self.roi,
            "measurement": self.display_measurement(),
            "calibration": self.calibration,
            "quality": self.quality,
        })
        return msg


@dataclass
class RespirationState:
    device_id: str
    session_id: str
    state: str
    signal: dict[str, Any] = field(default_factory=dict)
    gating: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> dict[str, Any]:
        assert self.state in RESPIRATION_STATES, f"bad state {self.state}"
        msg = _common(self.device_id, self.session_id)
        msg.update({
            "type": "respiration.state",
            "state": self.state,
            "signal": self.signal,
            "gating": self.gating,
            "quality": self.quality,
        })
        return msg


@dataclass
class ExposureRecommendation:
    device_id: str
    session_id: str
    inp: dict[str, Any]
    recommendation: dict[str, Any]
    guardrails: dict[str, Any]
    display: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> dict[str, Any]:
        msg = _common(self.device_id, self.session_id)
        msg.update({
            "type": "exposure.recommendation",
            "input": self.inp,
            "recommendation": self.recommendation,
            "guardrails": self.guardrails,
            "display": self.display,
        })
        return msg


def make_camera_frame_meta(device_id: str, session_id: str, frame_id: int,
                           camera: dict, stream: dict, shared_memory: dict,
                           quality: dict) -> dict[str, Any]:
    msg = _common(device_id, session_id)
    msg.update({
        "type": "camera.frame_meta",
        "frame_id": frame_id,
        "camera": camera, "stream": stream,
        "shared_memory": shared_memory, "quality": quality,
    })
    return msg


def make_operator_action(device_id: str, session_id: str, operator_id: str,
                         action: str, payload: dict | None = None) -> dict[str, Any]:
    assert action in OPERATOR_ACTIONS, f"bad action {action}"
    return {
        "schema_version": SCHEMA_VERSION,
        "type": "operator.action",
        "device_id": device_id,
        "session_id": session_id,
        "timestamp_ms": timestamp_ms(),
        "operator_id": operator_id,
        "action": action,
        "payload": payload or {},
    }


def as_dict(obj: Any) -> dict[str, Any]:
    """Best-effort: dataclass -> message dict, or passthrough dict."""
    if hasattr(obj, "to_message"):
        return obj.to_message()
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return dict(obj)
