# Verification & Validation

Test strategy for software, hardware integration, phantom tests, and fault injection. Every test case maps back to a risk control in [`docs/risk-management.md`](risk-management.md).

The key question for every test is not "does the algorithm return the right answer in ideal conditions?" — it's "does the system fail safely when things go wrong?"

---

## Test Levels

| Level | Target | Purpose |
|-------|--------|---------|
| Unit | Individual functions / classes | Algorithms, LUT logic, schema validation |
| Integration | Service-to-service communication | API contracts, IPC correctness |
| Playback | Recorded depth streams (de-identified) | Regression testing without hardware |
| Hardware | Real camera + real board | FPS, temperature, connection stability |
| HIL | Real board + real camera + phantom | End-to-end scenario testing |
| Usability | Operator UI | Misuse prevention, workflow validation |
| Long-run | Full system | Memory leaks, thermal stability, FPS |

---

## Camera Static Accuracy

Tests the depth measurement chain, not the algorithm.

| Parameter | Method |
|-----------|--------|
| Target | Known-height rigid phantom blocks |
| Distances | 0.6 m, 1.0 m, 1.5 m, 2.0 m |
| Repeats | ≥ 30 per distance |
| Records | median, mean, std, valid_pixel_ratio |
| Pass | Within project-defined tolerance (TBD with clinical team) |

Run this at:
- Initial installation
- After any camera replacement or re-mount
- After any calibration parameter change

---

## Dynamic Breathing Phantom

Validates the gating algorithm against controlled motion, not a real patient.

| Parameter | Range |
|-----------|-------|
| Device | Stepper-motor linear actuator |
| Amplitude | 5 mm, 10 mm, 20 mm, 50 mm |
| Period | 2 s, 4 s, 6 s, irregular |
| Metrics | Peak detection accuracy, stable-window detection, abort detection, gating latency |

**Gating latency target:** ≤ 33 ms internal processing delay (≤ one 30 FPS frame).

Record false-stable rate (stable declared when motion is present) and false-abort rate (abort declared when motion has stopped) for each amplitude/period combination.

---

## Long-Run Stability

| Duration | Purpose |
|----------|---------|
| 8 hours | MVP gate |
| 24 hours | Pre-production gate |
| 72 hours | Final production validation |

Collect every minute: FPS, dropped-frame count, CPU/GPU temperature, memory RSS of camera_service. Flag any of:
- FPS below 95% of target for > 10 s
- RSS growing monotonically (leak pattern)
- Temperature above board-spec limits
- Service restart events

---

## Unit Tests

```bash
pytest tests/unit/ -v
```

| ID | Target | Pass Criteria |
|----|--------|--------------|
| UT-LUT-001 | LUT boundary values | Correct clamping at min/max thickness |
| UT-GATE-001 | dZ/dt calculation | Correct stable/unstable classification |
| UT-GATE-002 | d²Z/dt² calculation | Cough spike detected, normal breathing not |
| UT-SCHEMA-001 | JSON schema validation | Missing required fields caught |
| UT-AUDIT-001 | Hash chain | Single-entry tampering detected |
| UT-CONFIG-001 | Config validation | Invalid YAML blocked on load |
| UT-CONF-001 | All `confidence` fields | Values are in [0.0, 1.0], definitions consistent |

---

## Integration Tests

```bash
pytest tests/integration/ -v
```

| ID | Target | Pass Criteria |
|----|--------|--------------|
| IT-CAM-CORE-001 | camera_service → depth_processor | frame_meta received and parsed correctly |
| IT-CORE-UI-001 | api_gateway → WebSocket | UI receives respiration state within 200 ms |
| IT-AUDIT-001 | operator action → audit_logger | Event persisted with correct hash |
| IT-SAFE-001 | error event → safe state | Recommendations disabled within 2 s |

---

## Fault Injection Tests

Run against a real board with real camera. Each test maps to a risk control.

| ID | Injected Fault | Expected Result | Risk Control |
|----|---------------|----------------|:------------:|
| FI-001 | Camera USB disconnected | Safe state within 2 s, UI warning | RC-CAM-001 |
| FI-002 | PoE link dropped | Reconnect attempt × 3, safe state | RC-CAM-001 |
| FI-003 | Depth frame timestamp reversed | Frame discarded, logged | RC-CAM-002 |
| FI-004 | SDK process killed | systemd restarts within RestartSec, UI shows warning | RC-CAM-001 |
| FI-005 | Config file checksum tampered | Service refuses to start | RC-CAM-004 |
| FI-006 | Model file tampered | Previous model loaded or safe state | — |
| FI-007 | DB write fails (disk full simulation) | Audit error shown, capture assist limited | RC-UI-004 |
| FI-008 | Power cut during DB write | `PRAGMA integrity_check` passes after recovery | RC-UI-004 |
| FI-009 | Thermal throttle injected | UI warning, FPS degrades gracefully | — |
| FI-010 | Proceed without operator approval | Action blocked, no downstream effect | RC-EXP-004 |

---

## Audio Latency Measurement

`gating.yaml` has `audio_latency_offset_ms`. This value must be **measured per installation**, not assumed.

**Procedure:**

1. Connect a USB microphone or reference mic near the speaker.
2. Play the breath-hold cue via `audio_cue_service` and record the output with a DAW or `arecord`.
3. Compare the GStreamer pipeline start timestamp against the first audio transient in the recording.
4. Measure in 10 repetitions and take the mean.
5. Enter the result in `gating.yaml`.

| ID | Test | Pass Criteria |
|----|------|--------------|
| TC-AUDIO-001 | Per-device latency measurement | Measured value recorded and signed in calibration file |
| TC-AUDIO-002 | Latency repeatability | Std dev < 20 ms across 10 repetitions |

---

## Golden Test Suite

The Golden Test Suite (GTS) runs automatically after every update and before rollback decision.

| ID | Test | Pass Criteria |
|----|------|--------------|
| GTS-001 | Camera 30 FPS × 10 s continuous | ≥ 95% frames received |
| GTS-002 | Empty-bed calibration | Completes without error, profile signed |
| GTS-003 | Static phantom thickness | Within tolerance of reference measurement |
| GTS-004 | Breathing phantom stable detection | Stable state detected in ≥ 9/10 trials |
| GTS-005 | Safe state on camera disconnect | Recommendations disabled within 2 s |
| GTS-006 | Audit log hash chain | All entries verify |
| GTS-007 | WebSocket UI state update | Status change reflected in UI within 500 ms |

Failure in any GTS item triggers automatic rollback.

---

## Acceptance Criteria Summary

| Item | Target |
|------|--------|
| Depth FPS | ≥ 95% of target FPS sustained |
| Frame drop rate | Below project threshold |
| UI state update latency | ≤ 500 ms from event |
| Gating latency | ≤ 33 ms internal processing |
| Abort response | Safe state within 2 s of fault |
| Audit log integrity | Hash chain validates 100% |
| Manual mode access | Available in all fault states |
| Calibration | Empty-bed baseline acquirable at startup |

---

## Test Artifacts

```
tests/
  unit/
  integration/
  playback/        ← de-identified depth sequences
  hil/
  fixtures/

test-results/      ← generated, not committed
  unit-test-report.xml
  integration-test-report.xml
  camera-static-accuracy.csv
  breathing-phantom-result.csv
  long-run-8h-report.json
  long-run-72h-report.json
  fault-injection-report.md
  audio-latency-measurements.csv
  usability-observation.md
  release-test-summary.md
```
