# api-schema.md — 내부 API, 메시지 스키마, IPC 계약 문서

작성 대상: 시니어 개발자, 백엔드/임베디드/UI 개발자, QA  
관련 문서: `README.md`, `docs/camera.md`, `docs/deployment.md`, `docs/risk-management.md`

---

## 1. 목적

본 문서는 스마트 호흡 연동 및 체형 맞춤형 촬영 보조 시스템의 서비스 간 통신 계약, 메시지 스키마, 내부 API, WebSocket 이벤트, 감사로그 이벤트 구조를 정의한다.

시스템은 카메라 제조사와 보드 종류가 바뀌어도 상위 모듈이 동일한 메시지 계약을 사용하도록 설계한다.

---

## 2. 서비스 구성

```text
camera_service
  → depth_processor
    → respiration_gating
    → body_measurement
      → exposure_recommender
        → operator_ui
        → audit_logger

device_gateway(optional)
  ↔ workstation_agent(optional)
```

---

## 3. 통신 방식 원칙

| 구간 | 권장 방식 | 이유 |
|---|---|---|
| camera_service → depth_processor | Shared Memory Ring Buffer | Depth frame 대용량 복사 최소화 |
| depth_processor → gating/recommender | ZeroMQ PUB/SUB 또는 gRPC stream | 저지연 이벤트 전달 |
| backend → UI | WebSocket | 실시간 상태 표시 |
| backend → local DB | SQLite WAL | 단일 장비 로컬 저장 |
| edge → workstation_agent | gRPC 또는 TCP JSON | 장비 연동 확장성 |
| service health | Unix domain socket / HTTP localhost | systemd health check |

---

## 4. 공통 메시지 규칙

### 4.1 Timestamp

모든 메시지는 `timestamp_ms`와 `monotonic_ms`를 함께 가진다.

```json
{
  "timestamp_ms": 1710000000000,
  "monotonic_ms": 5839201
}
```

- `timestamp_ms`: wall clock, 감사로그/사용자 표시용
- `monotonic_ms`: 실시간 처리 순서/latency 계산용

### 4.2 Versioning

모든 schema는 `schema_version`을 포함한다.

```json
{
  "schema_version": "1.0.0"
}
```

Breaking change 발생 시 major version을 올린다.

### 4.3 Device/Session ID

```json
{
  "device_id": "edge-xray-assist-001",
  "session_id": "sess_20260624_000001"
}
```

환자 식별정보는 기본 저장하지 않는다. 병원 연동 시에도 비식별 토큰만 사용한다.

---

## 5. CameraFrameMeta

Depth frame 원본은 shared memory에 저장하고, 이벤트 메시지는 metadata만 전달한다.

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

## 6. DepthSummary

Depth processor가 ROI 기반 요약값을 계산해 발행한다.

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
    "name": "chest",
    "x": 320,
    "y": 180,
    "width": 420,
    "height": 280,
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

## 7. RespirationState

호흡 게이팅 모듈의 실시간 상태 이벤트.

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

허용 상태값:

| state | 의미 |
|---|---|
| idle | 대기 |
| tracking | 호흡 추적 중 |
| cue_requested | 음성 안내 요청 |
| stable_breath_hold | 안정적 숨참기 |
| unstable | 불안정 |
| abort | 촬영 보조 중단 |
| timeout | 안정 구간 진입 실패 |
| manual_mode | 수동 모드 |

---

## 8. ExposureRecommendation

추천 kVp/mAs 이벤트. 초기 제품에서는 참고값이며 최종 설정은 작업자가 승인한다.

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
    "message": "추천값입니다. 최종 설정은 작업자가 확인해야 합니다.",
    "severity": "info"
  }
}
```

---

## 9. OperatorAction

작업자 UI에서 발생하는 이벤트.

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

허용 action:

| action | 의미 |
|---|---|
| start_session | 세션 시작 |
| calibrate_empty_bed | 빈 베드 캘리브레이션 |
| play_breath_cue | 호흡 안내 재생 |
| approve_recommendation | 추천값 승인 |
| reject_recommendation | 추천값 거부 |
| switch_manual_mode | 수동 모드 전환 |
| abort | 촬영 보조 중단 |
| end_session | 세션 종료 |

---

## 10. AuditEvent

감사로그는 append-only 구조로 저장한다.

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

DB 저장 필드:

```sql
CREATE TABLE audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  audit_id TEXT NOT NULL UNIQUE,
  timestamp_ms INTEGER NOT NULL,
  device_id TEXT NOT NULL,
  session_id TEXT,
  event_category TEXT NOT NULL,
  event_name TEXT NOT NULL,
  severity TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  prev_hash TEXT,
  event_hash TEXT NOT NULL
);
```

---

## 11. ErrorEvent

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
  "recommended_operator_action": "수동 모드로 전환하거나 카메라 연결을 확인하세요."
}
```

오류 코드 예시:

| code | 의미 | Safe State |
|---|---|---|
| CAMERA_DISCONNECTED | 카메라 연결 끊김 | yes |
| FRAME_DROP_EXCEEDED | 프레임 누락 임계 초과 | yes |
| CALIBRATION_MISSING | 캘리브레이션 없음 | yes |
| ROI_NOT_FOUND | 흉부 ROI 검출 실패 | yes |
| LOW_CONFIDENCE | 측정 신뢰도 낮음 | yes |
| AUDIO_DEVICE_MISSING | 오디오 출력 장치 없음 | no/partial |
| DB_WRITE_FAILED | 감사로그 저장 실패 | yes |
| MODEL_SIGNATURE_INVALID | 모델 서명 오류 | yes |
| CONFIG_SIGNATURE_INVALID | 설정 서명 오류 | yes |

---

## 12. Local REST API

UI 또는 진단 도구에서 사용하는 localhost API.

### 12.1 Health

```http
GET /api/v1/health
```

Response:

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

### 12.2 Current State

```http
GET /api/v1/state
```

Response:

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

### 12.3 Start Session

```http
POST /api/v1/sessions
Content-Type: application/json
```

Request:

```json
{
  "body_region": "chest_pa",
  "patient_mode": "adult"
}
```

Response:

```json
{
  "session_id": "sess_20260624_000001",
  "status": "started"
}
```

### 12.4 Operator Approval

```http
POST /api/v1/operator/approve
```

Request:

```json
{
  "session_id": "sess_001",
  "recommendation_id": "rec_001",
  "operator_id": "op_hash_8a31"
}
```

Response:

```json
{
  "status": "accepted",
  "audit_id": "audit_000000124"
}
```

---

## 13. WebSocket Events

Endpoint:

```text
ws://localhost:8080/ws/v1/events
```

구독 이벤트:

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

UI는 WebSocket 이벤트를 기준으로 실시간 화면을 갱신한다.

---

## 14. Workstation Agent API optional

Phase 2에서만 사용한다.

```protobuf
syntax = "proto3";

service WorkstationAgent {
  rpc SendRecommendation(ExposureRecommendationRequest) returns (AgentAck);
  rpc GetAgentStatus(AgentStatusRequest) returns (AgentStatusResponse);
}

message ExposureRecommendationRequest {
  string schema_version = 1;
  string device_id = 2;
  string session_id = 3;
  double kvp = 4;
  double mas = 5;
  string body_region = 6;
  bool operator_approval_required = 7;
}

message AgentAck {
  bool accepted = 1;
  string message = 2;
}
```

주의:

- Agent는 X-ray console을 직접 조작하기 전에 사용자 승인 상태를 확인해야 한다.
- UI automation 방식은 장비 SW 변경에 취약하므로 제품화 전 제조사 API 확보가 필요하다.

---

## 15. Schema Validation

권장:

- JSON Schema로 메시지 검증
- protobuf 사용 시 `.proto` 버전 관리
- schema breaking change 감지 테스트
- 저장 전 payload hash 생성

JSON Schema 예시:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RespirationState",
  "type": "object",
  "required": ["schema_version", "type", "device_id", "session_id", "timestamp_ms", "state"],
  "properties": {
    "schema_version": { "type": "string" },
    "type": { "const": "respiration.state" },
    "device_id": { "type": "string" },
    "session_id": { "type": "string" },
    "timestamp_ms": { "type": "integer" },
    "state": {
      "enum": ["idle", "tracking", "cue_requested", "stable_breath_hold", "unstable", "abort", "timeout", "manual_mode"]
    }
  }
}
```

---

## 16. 결론

상위 모듈은 카메라 제조사별 SDK에 직접 의존하지 않고, 본 문서의 표준 메시지 계약을 통해 Depth 요약값, 호흡 상태, 추천값, 감사로그를 주고받는다. 초기 구현은 JSON + ZeroMQ/WebSocket으로 빠르게 시작하고, 제품화 단계에서는 gRPC/protobuf와 shared memory ring buffer를 함께 사용한다.
