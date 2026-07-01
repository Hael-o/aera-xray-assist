"""Error codes and safe-state policy (api-schema.md ErrorEvent table).

Safe state = recommendations disabled, UI flashes Manual Mode. The X-ray
machine's manual workflow is NEVER affected — this system is an overlay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .. import SCHEMA_VERSION
from .clock import timestamp_ms

# code -> (module, enters_safe_state). "partial" -> degrade but do not full safe-state.
ERROR_CODES: dict[str, tuple[str, object]] = {
    "CAMERA_DISCONNECTED":     ("camera_service", True),
    "FRAME_DROP_EXCEEDED":     ("camera_service", True),
    "CALIBRATION_MISSING":     ("depth_processor", True),
    "CALIBRATION_DRIFT":       ("depth_processor", True),
    "ROI_NOT_FOUND":           ("depth_processor", True),
    "LOW_CONFIDENCE":          ("depth_processor", True),
    "AUDIO_DEVICE_MISSING":    ("respiration_gating", "partial"),
    "DB_WRITE_FAILED":         ("audit_logger", True),
    "MODEL_SIGNATURE_INVALID": ("exposure_recommender", True),
    "CONFIG_SIGNATURE_INVALID": ("any", True),
}


def enters_safe_state(code: str) -> bool:
    return ERROR_CODES.get(code, ("", True))[1] is True


@dataclass
class ErrorEvent:
    device_id: str
    code: str
    message: str
    module: Optional[str] = None
    session_id: Optional[str] = None
    recommended_operator_action: Optional[str] = None
    severity: str = "error"

    def to_message(self) -> dict:
        module = self.module or ERROR_CODES.get(self.code, ("unknown", True))[0]
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "system.error",
            "device_id": self.device_id,
            "session_id": self.session_id,
            "timestamp_ms": timestamp_ms(),
            "module": module,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "safe_state_entered": enters_safe_state(self.code),
            "recommended_operator_action": self.recommended_operator_action
            or "Switch to manual mode or check the device.",
        }


class SafeStateError(Exception):
    """Raised internally to force the pipeline into safe state."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
