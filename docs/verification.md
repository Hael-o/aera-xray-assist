# Verification & validation

[← back to README](../README.md)

Distilled from [`en/files/verification-validation.md`](../en/files/verification-validation.md). The current repo ships the **unit + integration** levels (42 tests passing); the hardware/HIL/long-run levels are the on-device acceptance plan.

## Test levels

| Level | Target | Acceptance |
|---|---|---|
| **Unit** | functions, LUT logic, schema validation | `pytest tests/unit/ -v` |
| **Integration** | service-to-service IPC, API contracts | IT-* |
| **Playback** | recorded (de-identified) depth streams | regression without hardware |
| **Hardware** | real camera + board | FPS ≥ 95%, no thermal throttle |
| **HIL** | camera + board + phantom | end-to-end + fault injection |
| **Usability** | operator UI | misuse prevention, workflow |
| **Long-run** | full system | 8 h (MVP) · 24 h (pre-prod) · 72 h (final) |

## Golden Test Suite (GTS-*)

| ID | Check |
|---|---|
| GTS-001 | camera 30 fps × 10 s → ≥ 95% frames |
| GTS-002 | empty-bed calibration → completes, profile signed |
| GTS-003 | static phantom thickness → within tolerance |
| GTS-004 | breathing phantom stable detection → ≥ 9/10 trials |
| GTS-005 | safe state on disconnect → recommendations disabled ≤ 2 s |
| GTS-006 | audit log hash chain → all entries verify |
| GTS-007 | WebSocket UI state → reflected ≤ 500 ms |

## Unit tests (UT-*)

`UT-LUT-001` LUT boundary values + clamping · `UT-GATE-001` dZ/dt calc + stable/unstable classification · `UT-GATE-002` d²Z/dt² + cough-spike detection · `UT-SCHEMA-001` JSON schema validation catches missing fields · `UT-AUDIT-001` hash chain detects tampering · `UT-CONFIG-001` invalid YAML blocked · `UT-CONF-001` all confidence fields in [0.0, 1.0].

## Integration tests (IT-*)

`IT-CAM-CORE-001` camera→depth frame_meta parsed · `IT-CORE-UI-001` gateway→WebSocket respiration within 200 ms · `IT-AUDIT-001` operator action persisted with correct hash · `IT-SAFE-001` error → safe state within 2 s.

## Fault injection (FI-*)

| ID | Injected fault | Expected | Control |
|---|---|---|---|
| FI-001 | camera USB disconnected | safe state ≤ 2 s, UI warning | RC-CAM-001 |
| FI-002 | PoE link dropped | 3 reconnect attempts, safe state | RC-CAM-001 |
| FI-003 | frame timestamp reversed | frame discarded, logged | RC-CAM-002 |
| FI-004 | SDK process killed | systemd restart, UI warning | RC-CAM-001 |
| FI-005 | config checksum tampered | service refuses start | RC-CAM-004 |
| FI-006 | model file tampered | previous model or safe state | — |
| FI-007 | DB write fails (disk full) | audit error, assist limited | RC-UI-004 |
| FI-008 | power cut during DB write | `PRAGMA integrity_check` passes | RC-UI-004 |
| FI-009 | thermal throttle | UI warning, FPS degrades gracefully | — |
| FI-010 | proceed without approval | action blocked, no downstream | RC-EXP-004 |

## Key phantom & timing criteria

- **Static accuracy (TC-CAL-001)**: known-height rigid blocks at 0.6/1.0/1.5/2.0 m, ≥ 30 reps each; record median/mean/std/valid_pixel_ratio.
- **Breathing phantom (TC-GATE-003)**: stepper-motor actuator; amplitudes 5/10/20/50 mm; periods 2/4/6 s + irregular; gating latency ≤ 33 ms; metrics = peak-detection accuracy, stable-window detection, abort detection, false-stable / false-abort rates.
- **Audio latency (TC-AUDIO-001/002)**: measured per device (USB mic + DAW), mean of 10 reps into `gating.yaml`; std dev target < 20 ms.
- **Long-run**: sample every minute (FPS, dropped frames, CPU/GPU temp, RSS); flag FPS < 95% for > 10 s, monotonic RSS growth, temp over spec, or service restarts.

## Acceptance summary

| Item | Target |
|---|---|
| Depth FPS | ≥ 95% of target, sustained |
| UI state update latency | ≤ 500 ms from event |
| Gating latency | ≤ 33 ms internal |
| Abort response | safe state ≤ 2 s |
| Audit integrity | hash chain 100% valid |
| Manual mode access | available in all fault states |

Related: [Depth & gating](depth-and-gating.md) · [Safety, risk & regulatory](safety-risk-regulatory.md)
