# API Schema & Message Contracts

This document is the single source of truth for all inter-service message schemas, IPC contracts, WebSocket events, local REST endpoints, and audit log structures. Upper services must not depend on vendor SDK types — they only ever see the types defined here.

---

## Principles

- **`timestamp_ms`** everywhere for wall clock (audit, display). **`monotonic_ms`** for latency and ordering calculations. Both are in milliseconds. No nanoseconds, no mixing.
- **`schema_version`** is semver (`"1.0.0"`). Major version bump on any breaking change.
- **`device_id`** and **`session_id`** travel on every message. Patient identifiers are never stored — hospital integration uses anonymized tokens only.
- Raw depth frames live in shared memory. Messages carry metadata and summaries, never pixel data.

---

## Service Communication Map

```
camera_service
  │  shared memory ring buffer (depth frames)
  ▼
depth_processor
  │  ZeroMQ PUB/SUB or gRPC stream (DepthSummary)
  ├──► respiration_gating
  │         │  (RespirationState)
  └──► exposure_recommender
            │  (ExposureRecommendation)
            ├──► api_gateway ──► WebSocket ──► Operator UI
            └──► audit_logger ──► SQLite

device_gateway  ← Phase 2+ only
  ↔ workstation_agent
```

| Segment | Transport | Reason |
|---------|-----------|--------|
| camera → depth_processor | Shared memory ring buffer | Avoid copying ~100 MB/s of frame data |
| depth_processor → gating/recommender | ZeroMQ PUB/SUB or gRPC stream | Low-latency event delivery |
| api_gateway → UI | WebSocket | Real-time state display |
| services → SQLite | SQLite WAL | Local single-device audit storage |
| edge → workstation agent | gRPC or TCP JSON | Device integration (Phase 2+) |

---

## Common Fields

Every message carries these:

```json
{
  "schema_version": "1.0.0",
  "timestamp_ms": 1710000000000,
  "monotonic_ms": 5839201,
  "device_id": "edge-xray-assist-001",
  "session_id": "sess_20260624_000001"
}
```

---

## CameraFrameMeta

`camera_service` publishes this after writing each frame to shared memory. Consumers use the `shared_memory` fields to read the actual pixels.

```json
{
  "schema_version": "1.0.0",
  "type": "camera.frame_meta",
  "device_id": "edge-001",
  "session_id": "sess_001",
  "frame_id": 123456,
  "timestamp_ms": 1710000000000,
  "monotonic_ms": 5839201,
  "camera": {
    "vendor": "intel_realsense",
    "model": "D455",
    "serial": "1234567890",
    "firmware": "5.x.x",
    "sdk": "librealsense2"
  },
  "stream": {
    "depth_width": 1280,
    "depth_height": 720,
    "depth_fps": 30,
    "format": "z16",
    "depth_scale_m": 0.001
  },
  "shared_memory": {
    "name": "/xray_depth_ring_0",
    "slot_index": 17,
    "bytes": 1843200
  },
  "quality": {
    "dropped_frames": 0,
    "usb_speed": "super_speed",
    "temperature_c": 42.5,
    "confidence": 0.98
  }
}
```

---

## DepthSummary

`depth_processor` publishes this after computing ROI statistics from the shared memory frame.

```json
{
  "schema_version": "1.0.0",
  "type": "depth.summary",
  "device_id": "edge-001",
  "session_id": "sess_001",
  "frame_id": 123456,
  "timestamp_ms": 1710000000000,
  "monotonic_ms": 5839201,
  "roi": {
    "name": "chest_pa",
    "x": 320, "y": 180, "width": 420, "height": 280,
    "confidence": 0.94
  },
  "measurement": {
    "median_depth_mm": 874.2,
    "mean_depth_mm": 876.8,
    "std_depth_mm": 4.6,
    "valid_pixel_ratio": 0.91,
    "estimated_thickness_mm": 238.5
  },
  "calibration": {
    "profile_id": "calib_room_a_20260624",
    "bed_origin_mm": 1112.7,
    "extrinsic_version": "2026.06.24"
  },
  "quality": {
    "ir_saturation": false,
    "motion_artifact": false,
    "clothing_artifact_score": 0.12,
    "confidence": 0.93
  }
}
```

---

## RespirationState

`respiration_gating` publishes this at every analysis tick (≥ 30 Hz target).

```json
{
  "schema_version": "1.0.0",
  "type": "respiration.state",
  "device_id": "edge-001",
  "session_id": "sess_001",
  "timestamp_ms": 1710000000000,
  "monotonic_ms": 5839201,
  "state": "stable_breath_hold",
  "signal": {
    "z_mm": 874.2,
    "dz_dt_mm_s": 0.8,
    "d2z_dt2_mm_s2": 0.05,
    "peak_phase": "plateau",
    "stable_duration_ms": 1320,
    "breathing_period_ms": 4100
  },
  "gating": {
    "window_open": true,
    "ready_to_capture": true,
    "abort": false,
    "reason": null
  },
  "quality": {
    "confidence": 0.91,
    "frame_drop_detected": false,
    "motion_artifact": false
  }
}
```

**Valid states:**

| State | Meaning |
|-------|---------|
| `idle` | Waiting for session start |
| `tracking` | Monitoring breathing waveform |
| `cue_requested` | Audio breath-hold cue triggered |
| `stable_breath_hold` | Patient is holding breath in stable window |
| `unstable` | Motion above threshold |
| `abort` | Session aborted (cough, motion spike, camera fault) |
| `timeout` | Stable window not reached within T_timeout |
| `manual_mode` | Operator overrode to manual |

---

## ExposureRecommendation

Recommendation values are reference-only. The operator approves before anything happens.

```json
{
  "schema_version": "1.0.0",
  "type": "exposure.recommendation",
  "device_id": "edge-001",
  "session_id": "sess_001",
  "timestamp_ms": 1710000000000,
  "monotonic_ms": 5839201,
  "input": {
    "estimated_thickness_mm": 238.5,
    "body_region": "chest_pa",
    "patient_mode": "adult",
    "confidence": 0.92
  },
  "recommendation": {
    "kvp": 82,
    "mas": 15.0,
    "source": "lut_v1.3.0",
    "model_hash": "sha256:...",
    "confidence": 0.88,
    "operator_approval_required": true
  },
  "guardrails": {
    "within_min_max": true,
    "pediatric_limit_applied": false,
    "bariatric_offset_applied": false,
    "manual_review_required": false
  },
  "display": {
    "message": "Reference values — operator confirmation required before use.",
    "severity": "info"
  }
}
```

Valid `body_region` values: `chest_pa`, `chest_lateral`, `abdomen_ap`, `pelvis_ap`. `chest_pa` (Posterior-Anterior) and `chest_ap` (Anterior-Posterior) are **different clinical projections** — do not use them interchangeably.

Valid `patient_mode` values: `adult`, `pediatric`, `bariatric`.

---

## OperatorAction

Events from the operator UI.

```json
{
  "schema_version": "1.0.0",
  "type": "operator.action",
  "device_id": "edge-001",
  "session_id": "sess_001",
  "timestamp_ms": 1710000000000,
  "operator_id": "op_hash_8a31",
  "action": "approve_recommendation",
  "payload": {
    "recommendation_id": "rec_001",
    "kvp": 82,
    "mas": 15.0,
    "note": "confirmed on console"
  }
}
```

**Valid actions:**

| Action | Meaning |
|--------|---------|
| `start_session` | Begin a capture session |
| `calibrate_empty_bed` | Trigger bed calibration |
| `play_breath_cue` | Trigger audio guidance |
| `approve_recommendation` | Confirm suggested kVp/mAs |
| `reject_recommendation` | Decline suggested kVp/mAs |
| `switch_manual_mode` | Override to manual |
| `abort` | Stop capture assist |
| `end_session` | Close session |

---

## AuditEvent

Audit records are append-only and form a SHA-256 hash chain. Every record depends on the previous one — a break in the chain indicates tampering.

```json
{
  "schema_version": "1.0.0",
  "type": "audit.event",
  "audit_id": "audit_000000123",
  "device_id": "edge-001",
  "session_id": "sess_001",
  "timestamp_ms": 1710000000000,
  "event_category": "recommendation",
  "event_name": "recommendation_generated",
  "severity": "info",
  "actor": {
    "type": "system",
    "id": "exposure_recommender"
  },
  "payload_hash": "sha256:...",
  "prev_hash": "sha256:...",
  "event_hash": "sha256:..."
}
```

**SQLite schema:**

```sql
CREATE TABLE audit_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  audit_id      TEXT    NOT NULL UNIQUE,
  timestamp_ms  INTEGER NOT NULL,
  device_id     TEXT    NOT NULL,
  session_id    TEXT,
  event_category TEXT   NOT NULL,
  event_name    TEXT    NOT NULL,
  severity      TEXT    NOT NULL,
  actor_type    TEXT    NOT NULL,
  actor_id      TEXT    NOT NULL,
  payload_json  TEXT    NOT NULL,
  payload_hash  TEXT    NOT NULL,
  prev_hash     TEXT,
  event_hash    TEXT    NOT NULL
);

PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;
```

Hash chain computation:

```python
import hashlib, json

def compute_event_hash(payload: dict, prev_hash: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return "sha256:" + hashlib.sha256(
        (prev_hash + canonical).encode()
    ).hexdigest()
```

**Important**: wall-clock timestamps are not guaranteed to be monotonic (NTP can adjust them). Use `id` (AUTOINCREMENT) for ordering, not `timestamp_ms`.

---

## ErrorEvent

```json
{
  "schema_version": "1.0.0",
  "type": "system.error",
  "device_id": "edge-001",
  "session_id": "sess_001",
  "timestamp_ms": 1710000000000,
  "module": "camera_service",
  "code": "CAMERA_DISCONNECTED",
  "severity": "error",
  "message": "Depth camera disconnected",
  "safe_state_entered": true,
  "recommended_operator_action": "Switch to manual mode or check camera connection."
}
```

**Error codes:**

| Code | Module | Enters Safe State |
|------|--------|:-----------------:|
| `CAMERA_DISCONNECTED` | camera_service | ✓ |
| `FRAME_DROP_EXCEEDED` | camera_service | ✓ |
| `CALIBRATION_MISSING` | depth_processor | ✓ |
| `CALIBRATION_DRIFT` | depth_processor | ✓ |
| `ROI_NOT_FOUND` | depth_processor | ✓ |
| `LOW_CONFIDENCE` | depth_processor | ✓ |
| `AUDIO_DEVICE_MISSING` | respiration_gating | partial |
| `DB_WRITE_FAILED` | audit_logger | ✓ |
| `MODEL_SIGNATURE_INVALID` | exposure_recommender | ✓ |
| `CONFIG_SIGNATURE_INVALID` | any | ✓ |

---

## Local REST API

Base URL: `http://localhost:8080/api/v1`

### Health

```
GET /health
```

```json
{
  "status": "ok",
  "device_id": "edge-001",
  "uptime_s": 12345,
  "services": {
    "camera_service": "ok",
    "depth_processor": "ok",
    "respiration_gating": "ok",
    "audit_logger": "ok"
  }
}
```

### Current State

```
GET /state
```

```json
{
  "session_id": "sess_001",
  "mode": "operator_assist",
  "camera": "connected",
  "calibration": "valid",
  "respiration_state": "tracking",
  "safe_state": false
}
```

### Start Session

```
POST /sessions
Content-Type: application/json

{ "body_region": "chest_pa", "patient_mode": "adult" }
```

```json
{ "session_id": "sess_20260624_000001", "status": "started" }
```

### Operator Approval

```
POST /operator/approve

{
  "session_id": "sess_001",
  "recommendation_id": "rec_001",
  "operator_id": "op_hash_8a31"
}
```

```json
{ "status": "accepted", "audit_id": "audit_000000124" }
```

---

## WebSocket Events

```
ws://localhost:8080/ws/v1/events
```

Subscribe on connect:

```json
{
  "subscribe": [
    "depth.summary",
    "respiration.state",
    "exposure.recommendation",
    "system.error"
  ]
}
```

The UI rebuilds its display from these events. It should implement exponential-backoff reconnect with heartbeat/ping-pong — the browser's native `WebSocket` has no auto-reconnect.

---

## Workstation Agent (Phase 2+)

```protobuf
syntax = "proto3";

service WorkstationAgent {
  rpc SendRecommendation(ExposureRecommendationRequest) returns (AgentAck);
  rpc GetAgentStatus(AgentStatusRequest)               returns (AgentStatusResponse);
}

message ExposureRecommendationRequest {
  string schema_version           = 1;
  string device_id                = 2;
  string session_id               = 3;
  double kvp                      = 4;
  double mas                      = 5;
  string body_region              = 6;
  bool   operator_approval_required = 7;
}

message AgentAck {
  bool   accepted = 1;
  string message  = 2;
}
```

The agent must check operator approval state before writing to the X-ray console. UI automation is fragile and not suitable for production — get the manufacturer's API first.

---

## Schema Validation

All messages are validated against JSON Schema before processing. Schema files are in `schemas/`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RespirationState",
  "type": "object",
  "required": ["schema_version","type","device_id","session_id","timestamp_ms","state"],
  "properties": {
    "schema_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "type": { "const": "respiration.state" },
    "state": {
      "enum": ["idle","tracking","cue_requested","stable_breath_hold",
               "unstable","abort","timeout","manual_mode"]
    }
  }
}
```

Run schema regression tests against any breaking change:

```bash
pytest tests/unit/test_schemas.py -v
```
