"""JSON Schema validation for all messages (api-schema.md §Schema Validation).
Messages are validated before processing; a breaking change must fail tests."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

# repo_root/schemas
_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"

# message "type" -> schema filename
_TYPE_TO_SCHEMA = {
    "camera.frame_meta": "camera_frame_meta.schema.json",
    "depth.summary": "depth_summary.schema.json",
    "respiration.state": "respiration_state.schema.json",
    "exposure.recommendation": "exposure_recommendation.schema.json",
    "operator.action": "operator_action.schema.json",
    "audit.event": "audit_event.schema.json",
    "system.error": "error_event.schema.json",
}


@lru_cache(maxsize=None)
def _load_schema(filename: str) -> dict[str, Any]:
    with (_SCHEMA_DIR / filename).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_message(message: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError if the message violates its schema."""
    mtype = message.get("type")
    schema_file = _TYPE_TO_SCHEMA.get(mtype)
    if schema_file is None:
        raise jsonschema.ValidationError(f"unknown message type: {mtype!r}")
    jsonschema.validate(message, _load_schema(schema_file))


def is_valid(message: dict[str, Any]) -> bool:
    try:
        validate_message(message)
        return True
    except jsonschema.ValidationError:
        return False
