# Safety, risk & regulatory

[← back to README](../README.md)

Distilled from [`en/files/regulatory.md`](../en/files/regulatory.md) and [`risk-management.md`](../en/files/risk-management.md). Informational, **not legal advice**.

## Device classification by phase

| Phase | Scope | Risk |
|---|---|---|
| 1 — Operator Assist *(this repo)* | reference-only suggestions, operator approval | Low–Medium |
| 2 — Workstation Agent | semi-automatic parameter entry, indirect control | Medium–High |
| 3 — Generator Direct | direct X-ray control | High |

**Phase 1 has zero electrical connection to the X-ray equipment** — which deliberately excludes it from higher electrical-safety scope. This is the central regulatory argument for the reference-only design.

## Standards invoked

| Standard | Application |
|---|---|
| **ISO 13485** | QMS — design controls, change control, CAPA |
| **ISO 14971** | risk management (hazard analysis, risk scoring) |
| **IEC 62304** | software lifecycle — requirements, architecture, V&V, maintenance; safety classes |
| **IEC 62366-1** | usability — operator UI, warnings, manual override |
| **IEC 60601-1** | electrical safety (if mains-powered) |
| **IEC 60601-1-2** | EMC — X-ray room EM environment |
| **Personal Data Protection Act** | RGB/depth handling, de-identification |
| **Medical Device Cybersecurity Guidance** | update signing, access control, audit logging |

### Software safety classes (working assumption, IEC 62304)

`camera_service` · `depth_processor` · `respiration_gating` · `exposure_recommender` · `operator_ui` → **Class B or C**; `audit_logger` → **B**; `device_gateway` (Phase 3) → **C**.

### Requirement-trace ID prefixes

`UN-` user need · `SYS-` system req · `SW-` software req · `HW-` hardware req · `RISK-`/`RC-` risk control · `TC-` test case.

## Risk scoring (ISO 14971)

`RPN = Severity × Occurrence × Detectability` (rough guide). Severity S1 (negligible) → S5 (critical, unintended exposure). Any S4+ hazard gets individual review regardless of RPN.

## Top hazards & controls

| ID | Hazard | Control | Verification |
|---|---|---|---|
| H-001 | Thickness mismeasurement | empty-bed calibration, drift check, confidence display | TC-CAL-001 (static phantom) |
| H-002 | Breathing stability misjudged | dZ/dt + d²Z/dt² gating, abort on spike | TC-GATE-003 (breathing phantom) |
| H-003 | Overexposure suggestion | hard kVp/mAs limits, operator approval, modes | TC-LUT-002 (boundary) |
| H-004 | Underexposure suggestion | lower limits enforced, confidence-gated | phantom + replay |
| H-005 | Operator misreads UI | "reference only" labels, separate approve button, warning colour | TC-UI-004 (usability) |
| H-006 | Camera hardware fault | watchdog, auto-reconnect, safe state | FI-001, FI-002 |
| H-007 | Audio guidance delay | ALSA direct output, per-device latency cal | TC-AUDIO-001 |
| H-008 | Audit log lost | SQLite WAL + FULL sync, hash chain, power-loss test | FI-008 |
| H-009 | Patient data exposure | RGB disabled by default, ROI masking, no PII | privacy review |
| H-010 | Model degradation | signed models, golden test suite, rollback | regression |
| H-011 | Unintended X-ray trigger | **Phase 1 has no hardware connection** — electrically excluded | HIL (Phase 3) |
| H-012 | Manual mode inaccessible | manual always visible + accessible | FI-010 |

## Safe state

Triggered immediately on any of: camera disconnected/not found · consecutive frame drops over threshold · calibration missing/expired/invalid signature · ROI detection failed · confidence below minimum · motion/cough · recommender exception · model/config signature invalid · DB write failure or storage full.

**Behaviour**: recommendations disabled · all automated inputs disabled · operator directed to manual workflow · audit event recorded · audio stopped · the X-ray machine's manual workflow untouched.

## Representative risk controls

`RC-CAM-001` no camera → no recommendations · `RC-CAM-002` reversed/missing timestamps discarded · `RC-CAM-003` low ROI confidence → manual mode · `RC-CAM-004` missing/mismatched calibration blocks assist · `RC-GATE-001` stability requires min sustained duration · `RC-GATE-002` cough/motion → abort · `RC-EXP-001` recommendations must not exceed LUT bounds · `RC-EXP-002` confidence + LUT version on every recommendation · `RC-UI-001` suggested vs. confirmed visually distinct · `RC-UI-002` manual override always accessible · `RC-UI-004` operator approval → audit.

## Regulatory posture summary

Reference-only; hard operator-approval gate; QA-approved, versioned, source-logged LUT bounds; all models pre-validated, Ed25519-signed offline, gated by the Golden Test Suite before activation; **no post-deployment self-learning in any phase**.

Related: [Exposure & safety](exposure-and-safety.md) · [Verification](verification.md) · [Audit hash chain](audit-chain.md)
