# Risk Management

ISO 14971 approach. This is a living document — review it when the scope changes, before each release, and whenever a real incident occurs.

---

## Scope

**In scope (Phase 1 — Operator Assist):**
- 3D depth-based patient thickness and body-region measurement
- Breathing stability detection and gating
- Suggested kVp/mAs display
- Operator approval workflow
- Audit log

**Out of scope (handled in future phases):**
- X-ray generator direct control
- Autonomous capture without operator approval
- Diagnostic image interpretation
- Post-deployment self-learning model updates

---

## Risk Scoring

### Severity

| Level | Meaning | Example |
|-------|---------|---------|
| S1 | Negligible | Temporary UI confusion, retry needed |
| S2 | Minor | Workflow delay |
| S3 | Moderate | Retake likely, image quality degraded |
| S4 | Serious | Incorrect exposure, possible dose error |
| S5 | Critical | Unintended exposure, safety incident |

### Occurrence

| Level | Meaning |
|-------|---------|
| O1 | Unlikely |
| O2 | Rare |
| O3 | Occasional |
| O4 | Likely |
| O5 | Very frequent |

### Detectability

| Level | Meaning |
|-------|---------|
| D1 | Automatically detected |
| D2 | Usually detectable |
| D3 | Sometimes detectable |
| D4 | Hard to detect |
| D5 | Nearly undetectable |

`RPN = S × O × D` is a rough guide. Any S4+ hazard gets individual review regardless of RPN.

---

## Hazard List

| ID | Hazard | Root Causes | Potential Harm |
|----|--------|------------|----------------|
| H-001 | Patient thickness mismeasurement | Calibration drift, garment noise, IR saturation | Inappropriate exposure suggestion |
| H-002 | Breathing stability misjudged | Frame drop, cough, motion | Retake, motion blur |
| H-003 | Overexposure suggestion | LUT error, pediatric/bariatric correction failure | Unnecessary dose |
| H-004 | Underexposure suggestion | Thickness underestimate, depth hole | Noisy image, retake |
| H-005 | Operator misreads UI | Suggestion vs. confirmed value confusion | Wrong console input |
| H-006 | Camera hardware fault | USB/PoE disconnect, SDK crash | Measurement unavailable |
| H-007 | Audio guidance delay | ALSA/mixer latency variance | Capture timing offset |
| H-008 | Audit log lost | DB failure, power cut | Loss of traceability |
| H-009 | Patient data exposure | RGB/Depth frame stored with identifiers | Privacy breach |
| H-010 | Model performance degradation | Unsigned update, validation bypass | Increased misjudgement rate |
| H-011 | Unintended X-ray trigger | Phase 3 relay/software fault | Safety incident |
| H-012 | Manual mode inaccessible | UI/service hang | Emergency workflow blocked |

---

## Risk Controls

| Hazard | Initial S/O/D | Control | Verification | Residual |
|--------|:-------------:|---------|-------------|---------|
| H-001 | 4/3/3 | Empty-bed calibration, drift check at startup, confidence display | Static phantom test (TC-CAL-001) | Review |
| H-002 | 3/3/3 | dZ/dt + d²Z/dt² gating, min stable duration, abort on spike | Breathing phantom test (TC-GATE-003) | Acceptable |
| H-003 | 4/2/3 | Hard kVp/mAs limits, operator approval, pediatric/bariatric modes | LUT boundary test (TC-LUT-002) | RA review |
| H-004 | 3/3/3 | Lower limits enforced, confidence-gated recommendation | Phantom + replay test | Review |
| H-005 | 4/2/3 | "Reference only" labeling, separate approval button, warning color | Usability test | Operator training |
| H-006 | 2/3/1 | Watchdog, auto-reconnect, safe state on fault | Fault injection FI-001, FI-002 | Acceptable |
| H-007 | 3/2/2 | ALSA direct output, per-device latency calibration | Latency measurement (TC-AUDIO-001) | Acceptable |
| H-008 | 3/2/3 | SQLite WAL + FULL sync, hash chain, power-loss test | Power-loss test (FI-008) | Acceptable |
| H-009 | 4/2/3 | RGB disabled by default, depth ROI masking, no PII in logs | Privacy review | Policy review |
| H-010 | 4/2/4 | Signed models only, golden test suite gate, rollback | Regression test | Excluded from Phase 1 |
| H-011 | 5/1/4 | Phase 1 has no hardware connection — electrically excluded | HIL safety test | Phase 3 only |
| H-012 | 4/2/2 | Manual mode always visible, always accessible | Usability + fault test (FI-010) | Review |

---

## Safe State

Any of the following conditions must immediately put the system into Safe State:

```
Safe State:
  - Exposure recommendation display disabled
  - All automated/semi-automated inputs disabled
  - Operator directed to manual X-ray workflow
  - Audit event recorded
  - Audio guidance stopped if applicable
```

**Triggers:**

- Camera disconnected or not found
- Consecutive depth frame drops exceed threshold
- Calibration missing, expired, or signature invalid
- ROI detection failed
- Measurement confidence below minimum threshold
- Patient motion / cough detected
- Recommendation engine exception
- Model or config file signature verification failed
- DB write failure or storage full

---

## Risk Control Requirements

### Camera / Depth Measurement

| ID | Requirement |
|----|-------------|
| RC-CAM-001 | If camera is not detected, the system must not display recommendations |
| RC-CAM-002 | Frames with reversed or missing timestamps must be discarded |
| RC-CAM-003 | If ROI confidence falls below threshold, switch to manual mode |
| RC-CAM-004 | Missing or version-mismatched calibration must block capture assist |

### Respiration Gating

| ID | Requirement |
|----|-------------|
| RC-GATE-001 | Stability judgment must require minimum sustained stable duration |
| RC-GATE-002 | Cough / sudden motion must trigger Abort state |
| RC-GATE-003 | Timeout must offer re-guidance or manual transition workflow |
| RC-GATE-004 | Audio guidance offset must be managed as a configurable, measured parameter |

### Exposure Recommender

| ID | Requirement |
|----|-------------|
| RC-EXP-001 | Recommendations must not exceed the bounds defined in the approved LUT |
| RC-EXP-002 | Confidence and source LUT version must accompany every recommendation |
| RC-EXP-003 | UI must display a warning when switching to pediatric or bariatric mode |
| RC-EXP-004 | Final capture parameters must be reviewed and confirmed by the operator |

### UI / Operator

| ID | Requirement |
|----|-------------|
| RC-UI-001 | Suggested values and actual console settings must be visually distinct |
| RC-UI-002 | Manual override must always be accessible |
| RC-UI-003 | Fault states must be communicated by color, text, and optionally audio |
| RC-UI-004 | Every operator approval event must be written to the audit log |

---

## Fault Injection Tests

These tests must pass before any release. See [`docs/verification-validation.md`](verification-validation.md) for detailed procedures.

| ID | Injected Fault | Expected Result |
|----|---------------|----------------|
| FI-001 | Camera USB disconnect | Safe state within 2 s, recommendation disabled, UI warning |
| FI-002 | PoE link drop | Reconnect attempts, safe state maintained |
| FI-003 | Depth frame timestamp error | Frame discarded, logged |
| FI-004 | SDK process crash | systemd restart, UI warning |
| FI-005 | Config file tampered | Signature check fails, service refuses to start |
| FI-006 | Model file tampered | Rollback to previous model or safe state |
| FI-007 | DB write failure | Audit error displayed, capture assist limited |
| FI-008 | Power cut during write | DB integrity check, WAL recovery |
| FI-009 | CPU/GPU thermal throttle | Performance warning, safe degradation |
| FI-010 | Attempt to proceed without operator approval | Action blocked, logged |

---

## Residual Risk Management

Residual risks are managed by:
- User manual explicitly stating system limitations
- "Reference only — operator confirmation required" shown on all recommendations
- Per-mode (pediatric/bariatric) UI warnings
- Manual workflow always available when system is degraded
- Per-hospital calibration verification at installation
- Post-market surveillance via field logs

---

## Traceability

| Risk ID | Requirement | Test Case | Evidence |
|---------|-------------|-----------|---------|
| H-001 | RC-CAM-004 | TC-CAL-001 | calibration_report.json |
| H-002 | RC-GATE-002 | TC-GATE-003 | breathing_phantom_result.csv |
| H-003 | RC-EXP-001 | TC-LUT-002 | lut_boundary_test.xml |
| H-005 | RC-UI-001 | TC-UI-004 | usability_test_report.pdf |
| H-008 | RC-UI-004 | TC-AUDIT-001 | audit_log_integrity.txt |
