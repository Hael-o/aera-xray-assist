"""Config loading + validation + signature gate.

Per camera.md / deployment.md, configs and calibration profiles carry an
Ed25519 signature; an unsigned or mismatched file must block startup
(CONFIG_SIGNATURE_INVALID -> safe state). The MVP ships a HMAC-SHA256
placeholder verifier behind the same interface so the gate is exercised in
tests; swap in real Ed25519 (pynacl) for production without touching callers."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any

import yaml

from .errors import SafeStateError

# Dev-only key. Production uses a per-device Ed25519 key from secure storage.
_DEV_SIGNING_KEY = os.environ.get("XRAY_CONFIG_KEY", "mvp-dev-key").encode()


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise SafeStateError("CONFIG_SIGNATURE_INVALID", f"config not found: {p}")
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # UT-CONFIG-001: invalid YAML blocked on load
        raise SafeStateError("CONFIG_SIGNATURE_INVALID", f"invalid YAML in {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise SafeStateError("CONFIG_SIGNATURE_INVALID", f"config must be a mapping: {p}")
    return data


def compute_signature(payload: bytes) -> str:
    """Placeholder signature (HMAC-SHA256). Replace with Ed25519 in production."""
    return "hmac:" + hmac.new(_DEV_SIGNING_KEY, payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, signature: str) -> bool:
    if signature == "PLACEHOLDER":
        # MVP fixtures: accept the well-known placeholder so the system boots
        # without a signing ceremony. Production rejects this.
        return os.environ.get("XRAY_ENV") != "production"
    expected = compute_signature(payload)
    return hmac.compare_digest(expected, signature)


def require_valid_config(data: dict[str, Any], required_keys: tuple[str, ...],
                         name: str) -> None:
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise SafeStateError(
            "CONFIG_SIGNATURE_INVALID",
            f"{name} missing required keys: {missing}",
        )
