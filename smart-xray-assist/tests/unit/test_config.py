"""UT-CONFIG-001 — Config validation: invalid YAML blocked on load
(verification-validation.md). A bad config must raise SafeStateError, never
silently load a partial/None config."""

from __future__ import annotations

import pytest

from xray_assist.common.config import (
    compute_signature,
    load_yaml,
    require_valid_config,
    verify_signature,
)
from xray_assist.common.errors import SafeStateError


def test_invalid_yaml_blocked_on_load(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: [unclosed\n  : nested broken")
    with pytest.raises(SafeStateError) as exc:
        load_yaml(bad)
    assert exc.value.code == "CONFIG_SIGNATURE_INVALID"


def test_missing_file_blocked(tmp_path):
    with pytest.raises(SafeStateError) as exc:
        load_yaml(tmp_path / "does_not_exist.yaml")
    assert exc.value.code == "CONFIG_SIGNATURE_INVALID"


def test_non_mapping_yaml_blocked(tmp_path):
    f = tmp_path / "list.yaml"
    f.write_text("- a\n- b\n")   # valid YAML, but a list not a mapping
    with pytest.raises(SafeStateError):
        load_yaml(f)


def test_valid_yaml_loads(tmp_path):
    f = tmp_path / "ok.yaml"
    f.write_text("gating:\n  timeout_ms: 10000\n")
    data = load_yaml(f)
    assert data["gating"]["timeout_ms"] == 10000


def test_require_valid_config_missing_keys():
    with pytest.raises(SafeStateError) as exc:
        require_valid_config({"metadata": {}}, ("metadata", "guardrails"), "lut.yaml")
    assert exc.value.code == "CONFIG_SIGNATURE_INVALID"


def test_signature_roundtrip():
    payload = b"calibration-bytes"
    sig = compute_signature(payload)
    assert verify_signature(payload, sig) is True
    assert verify_signature(payload, "hmac:" + "0" * 64) is False
