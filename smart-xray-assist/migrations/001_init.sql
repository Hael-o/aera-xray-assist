-- Audit event store. Append-only, SHA-256 hash chain (api-schema.md).
-- Ordering is by `id` (AUTOINCREMENT), NOT timestamp_ms (NTP can move wall clock).

CREATE TABLE IF NOT EXISTS audit_events (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  audit_id       TEXT    NOT NULL UNIQUE,
  timestamp_ms   INTEGER NOT NULL,
  device_id      TEXT    NOT NULL,
  session_id     TEXT,
  event_category TEXT    NOT NULL,
  event_name     TEXT    NOT NULL,
  severity       TEXT    NOT NULL,
  actor_type     TEXT    NOT NULL,
  actor_id       TEXT    NOT NULL,
  payload_json   TEXT    NOT NULL,
  payload_hash   TEXT    NOT NULL,
  prev_hash      TEXT,
  event_hash     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events (session_id);
CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_events (event_category);

-- Calibration profiles (camera.md). Signed; unsigned/mismatched blocks startup.
CREATE TABLE IF NOT EXISTS calibration_profiles (
  profile_id   TEXT PRIMARY KEY,
  created_at   TEXT NOT NULL,
  camera_serial TEXT,
  profile_json TEXT NOT NULL,
  signature    TEXT NOT NULL,
  loaded_at_ms INTEGER NOT NULL
);
