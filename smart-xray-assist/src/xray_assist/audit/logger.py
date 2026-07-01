"""audit_logger: append-only SQLite (WAL) with an application-level SHA-256 hash
chain (api-schema.md, tech-stack §7).

Each record's event_hash = sha256(prev_hash + canonical(payload)). A break in
the chain indicates tampering. Ordering is by `id` (AUTOINCREMENT), NOT
timestamp_ms — NTP can move the wall clock. The hash chain is built at the
application level (SQLite triggers are poor for canonicalisation/key mgmt)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from ..common.clock import timestamp_ms

GENESIS_HASH = "sha256:" + "0" * 64


def compute_payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def compute_event_hash(payload: dict[str, Any], prev_hash: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


class AuditLogger:
    def __init__(self, db_path: str | Path, device_id: str,
                 migration_sql: Optional[str | Path] = None) -> None:
        self.device_id = device_id
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # The pipeline driver thread writes; the FastAPI threadpool reads
        # (/api/v1/audit, /audit/verify). Share one connection across threads and
        # serialize every access with a lock — single-writer, low volume.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_db(migration_sql)
        self._seq = self._count()

    def _init_db(self, migration_sql: Optional[str | Path]) -> None:
        if migration_sql is not None:
            sql = Path(migration_sql).read_text(encoding="utf-8") \
                if Path(str(migration_sql)).exists() else str(migration_sql)
            self._conn.executescript(sql)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=FULL;")   # power-loss durability (FI-008)
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.commit()

    def _count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) AS n FROM audit_events")
            return int(cur.fetchone()["n"])

    def last_hash(self) -> str:
        with self._lock:
            cur = self._conn.execute(
                "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            return row["event_hash"] if row else GENESIS_HASH

    def append(self, event_category: str, event_name: str, payload: dict[str, Any],
               actor_type: str = "system", actor_id: str = "system",
               severity: str = "info", session_id: Optional[str] = None) -> dict[str, Any]:
        """Append one event; returns the AuditEvent message. Raises DB_WRITE_FAILED
        on failure (caller turns it into safe state)."""
        # whole read-modify-write is atomic so concurrent appends can't interleave
        with self._lock:
            self._seq += 1
            audit_id = f"audit_{self._seq:09d}"
            prev_hash = self.last_hash()
            payload_hash = compute_payload_hash(payload)
            event_hash = compute_event_hash(payload, prev_hash)
            ts = timestamp_ms()
            try:
                self._conn.execute(
                    """INSERT INTO audit_events
                       (audit_id, timestamp_ms, device_id, session_id, event_category,
                        event_name, severity, actor_type, actor_id, payload_json,
                        payload_hash, prev_hash, event_hash)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (audit_id, ts, self.device_id, session_id, event_category,
                     event_name, severity, actor_type, actor_id,
                     json.dumps(payload, sort_keys=True, separators=(",", ":")),
                     payload_hash, prev_hash, event_hash),
                )
                self._conn.commit()
            except sqlite3.Error as exc:
                self._seq -= 1
                from ..common.errors import SafeStateError
                raise SafeStateError("DB_WRITE_FAILED", f"audit write failed: {exc}") from exc

        return {
            "schema_version": "1.0.0", "type": "audit.event", "audit_id": audit_id,
            "device_id": self.device_id, "session_id": session_id, "timestamp_ms": ts,
            "event_category": event_category, "event_name": event_name,
            "severity": severity, "actor": {"type": actor_type, "id": actor_id},
            "payload_hash": payload_hash, "prev_hash": prev_hash,
            "event_hash": event_hash,
        }

    def recent(self, limit: int = 60) -> list[dict[str, Any]]:
        """Newest-first slice of the chain for the operator console audit panel.
        Ordered by `id` DESC (append order), NOT timestamp."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, audit_id, timestamp_ms, session_id, event_category,
                          event_name, severity, actor_id, payload_json, event_hash
                   FROM audit_events ORDER BY id DESC LIMIT ?""",
                (int(limit),)).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append({
                "seq": row["id"],
                "audit_id": row["audit_id"],
                "timestamp_ms": row["timestamp_ms"],
                "session_id": row["session_id"],
                "category": row["event_category"],
                "type": row["event_name"],
                "severity": row["severity"],
                "actor_id": row["actor_id"],
                "payload": json.loads(row["payload_json"]),
                "event_hash": row["event_hash"],
            })
        return out

    def verify_chain(self) -> bool:
        """Recompute the whole chain; return True iff every link verifies
        (UT-AUDIT-001 / GTS-006)."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT payload_json, prev_hash, event_hash
                   FROM audit_events ORDER BY id ASC""").fetchall()
        prev = GENESIS_HASH
        for row in rows:
            payload = json.loads(row["payload_json"])
            if row["prev_hash"] != prev:
                return False
            if compute_event_hash(payload, prev) != row["event_hash"]:
                return False
            prev = row["event_hash"]
        return True

    def close(self) -> None:
        self._conn.close()
