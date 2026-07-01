"""UT-AUDIT-001 — Hash chain: single-entry tampering detected
(verification-validation.md / GTS-006)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from xray_assist.audit.logger import AuditLogger

_MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"


@pytest.fixture
def audit(tmp_path):
    a = AuditLogger(tmp_path / "audit.db", "edge-001", migration_sql=_MIGRATION)
    yield a
    a.close()


def _seed(audit, n=5):
    for i in range(n):
        audit.append("session", f"event_{i}", {"i": i, "payload": f"data-{i}"},
                     session_id="sess_test")


def test_intact_chain_verifies(audit):
    _seed(audit)
    assert audit.verify_chain() is True


def test_single_entry_payload_tampering_detected(audit, tmp_path):
    _seed(audit)
    assert audit.verify_chain() is True

    # tamper with one row's payload directly in the DB
    conn = sqlite3.connect(tmp_path / "audit.db")
    row = conn.execute("SELECT id, payload_json FROM audit_events ORDER BY id LIMIT 1 OFFSET 2").fetchone()
    payload = json.loads(row[1])
    payload["payload"] = "TAMPERED"
    conn.execute("UPDATE audit_events SET payload_json=? WHERE id=?",
                 (json.dumps(payload, sort_keys=True, separators=(",", ":")), row[0]))
    conn.commit()
    conn.close()

    assert audit.verify_chain() is False


def test_hash_field_tampering_detected(audit, tmp_path):
    _seed(audit)
    conn = sqlite3.connect(tmp_path / "audit.db")
    conn.execute("UPDATE audit_events SET event_hash=? WHERE id=("
                 "SELECT id FROM audit_events ORDER BY id LIMIT 1 OFFSET 1)",
                 ("sha256:" + "f" * 64,))
    conn.commit()
    conn.close()
    assert audit.verify_chain() is False


def test_append_returns_linked_hashes(audit):
    e1 = audit.append("session", "first", {"a": 1})
    e2 = audit.append("session", "second", {"b": 2})
    # each event's prev_hash points at the previous event's hash
    assert e2["prev_hash"] == e1["event_hash"]
    assert e1["event_hash"].startswith("sha256:")
