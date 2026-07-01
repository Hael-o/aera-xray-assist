# Audit hash chain

[← back to README](../README.md) · [한국어](audit-chain.ko.md)

[`audit/logger.py`](../smart-xray-assist/src/xray_assist/audit/logger.py) · schema [`migrations/001_init.sql`](../smart-xray-assist/migrations/001_init.sql)

In a medical system, "what happened, when, and who approved it" must be tamper-evident after the fact. This uses an **append-only SQLite store + an application-level SHA-256 hash chain**.

## Principle — blockchain-style linking

Each event's hash includes the **previous event's hash**, so changing any record breaks every hash after it.

```
event_hash(n) = SHA-256( event_hash(n−1) + canonical(payload(n)) )

genesis ──► e1 ──► e2 ──► e3 ──► … ──► eN
            │      │      │
         prev=g  prev=h1 prev=h2   (each link seals the previous hash)
```

- `canonical(payload)` = `json.dumps(payload, sort_keys=True, separators=(",",":"))` — reproducible serialisation via sorted keys
- `GENESIS_HASH = "sha256:" + "0"*64`
- Ordering is by **`id` (AUTOINCREMENT)**, not `timestamp_ms` — NTP can move the wall clock.

```python
def compute_event_hash(payload: dict, prev_hash: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256((prev_hash + canonical).encode()).hexdigest()
```

## Audit event envelope

```json
{
  "schema_version": "1.0.0", "type": "audit.event",
  "audit_id": "audit_000000123", "device_id": "edge-001", "session_id": "sess_001",
  "timestamp_ms": 1710000000000,
  "event_category": "recommendation", "event_name": "recommendation_generated",
  "severity": "info", "actor": { "type": "system", "id": "exposure_recommender" },
  "payload_hash": "sha256:…", "prev_hash": "sha256:…", "event_hash": "sha256:…"
}
```

## Verification

`verify_chain()` recomputes the whole chain from genesis:

```python
prev = GENESIS_HASH
for row in rows_ordered_by_id:
    if row.prev_hash != prev:                         return False  # broken link
    if event_hash(payload, prev) != row.event_hash:   return False  # tampered payload
    prev = row.event_hash
return True
```

The console's **"Verify chain integrity"** button hits `GET /api/v1/audit/verify`, verifying this real server chain and showing `✓ N links verified`.

## Tamper model & limits

- The chain detects **modification and reordering**, but **not deletion of the entire DB**. Mitigation (from the specs): **daily external anchoring** — remote syslog, or USB export + off-device hash verification.
- Application-level chain is preferred over DB-level triggers: SQLite triggers can't prevent deletion and key management inside the DB is hard.
- **Config/model signature integrity**: calibration.json, exposure_lut.yaml, and model files are Ed25519-signed offline; an invalid signature blocks service start (`CONFIG_SIGNATURE_INVALID` / `MODEL_SIGNATURE_INVALID`).

## Durability & concurrency

- `PRAGMA journal_mode=WAL` + `synchronous=FULL` — power-loss durability (tested by fault injection FI-008)
- Audit DB write failure → `DB_WRITE_FAILED` → safe state (never swallowed)
- The driver thread (pipeline) and the FastAPI thread pool (REST) share one connection, so append/read are serialised with an `RLock`. The read-modify-write (seq · prev_hash · insert) is atomic, so concurrent appends never interleave.

## Table schema (summary)

```sql
audit_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,   -- ordering basis
  audit_id, timestamp_ms, device_id, session_id,
  event_category, event_name, severity, actor_type, actor_id,
  payload_json,                            -- canonical serialisation
  payload_hash, prev_hash, event_hash      -- hash chain
)
-- PRAGMA journal_mode=WAL; synchronous=FULL; foreign_keys=ON
```

Related: [API & realtime](api-and-realtime.md) · [Verification](verification.md)
