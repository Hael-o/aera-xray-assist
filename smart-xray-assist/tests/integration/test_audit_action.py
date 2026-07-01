"""IT-AUDIT-001 — operator action -> audit_logger: event persisted with correct
hash (verification-validation.md)."""

from __future__ import annotations

import sqlite3


def test_operator_action_persisted_with_valid_hash(orch):
    before = orch.audit._count()

    result = orch.operator_action(
        "approve_recommendation", operator_id="operator_1",
        payload={"recommendation_id": "rec_000001"})

    assert result["status"] == "accepted"
    assert "audit_id" in result

    # one new row persisted
    assert orch.audit._count() == before + 1
    # hash chain still verifies after the new entry
    assert orch.audit.verify_chain() is True

    # the action is actually on disk with category operator_action
    conn = sqlite3.connect(orch.audit.db_path)
    row = conn.execute(
        "SELECT event_category, event_name, actor_type, event_hash, prev_hash "
        "FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "operator_action"
    assert row[1] == "approve_recommendation"
    assert row[2] == "operator"
    assert row[3].startswith("sha256:") and row[4].startswith("sha256:")


def test_approval_recorded_before_effect(orch):
    # the approval must be auditable and queryable as approved
    orch.operator_action("approve_recommendation", "operator_1",
                         {"recommendation_id": "rec_000042"})
    assert orch.is_approved("rec_000042") is True
    assert orch.audit.verify_chain() is True
