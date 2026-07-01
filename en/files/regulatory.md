# Regulatory Notes

This document is not legal advice or a regulatory submission. It lays out how we're thinking about classification and what we're building toward from a quality system perspective. Actual classification and submission strategy requires a regulatory affairs specialist and will depend on the final intended use, the extent of X-ray control, and the market.

---

## Product Scope by Phase

| Phase | Function | X-ray Control | Regulatory Risk |
|-------|----------|:-------------:|:---------------:|
| 1 — Operator Assist | Thickness + breathing display, suggested parameters | None | Low–Medium |
| 2 — Workstation Agent | Semi-auto parameter entry, operator approval required | Indirect | Medium–High |
| 3 — Generator Direct | Direct generator control | Yes | High |
| 4 — Controlled Model Update | Validated model deployment | Depends | High |
| 5 — On-device Learning | Limited continual learning (research) | Depends | High |

**Phase 1 intended use statement:**

> This system uses a 3D depth sensor to measure patient body thickness and breathing stability, and provides reference kVp/mAs suggestions to qualified X-ray operators before exposure. Final exposure parameters and capture decisions are made by the operator.

Things to avoid saying in any documentation or marketing:
- "Automatically determines optimal dose"
- "Captures without operator intervention"
- "Guarantees optimal kVp/mAs for all patients"
- "Eliminates retakes"

---

## Standards Landscape

| Standard | Why it matters here |
|----------|-------------------|
| ISO 13485 | QMS — design controls, change control, CAPA |
| ISO 14971 | Risk management — see [`docs/risk-management.md`](risk-management.md) |
| IEC 62304 | Software lifecycle — requirements, architecture, V&V, maintenance |
| IEC 62366-1 | Usability — operator UI, warnings, manual override |
| IEC 60601-1 | Electrical safety — applies if the device is powered from mains |
| IEC 60601-1-2 | EMC — X-ray room EM environment |
| Personal Data Protection Act | RGB/Depth data handling, de-identification |
| Medical device cybersecurity guidance | Update signing, access control, audit logging |

---

## Software Safety Classification (IEC 62304)

We don't pre-assign safety classes in this document — the final class depends on the harm analysis. As a working assumption:

| Module | Potential Harm | Working Class |
|--------|---------------|:-------------:|
| `camera_service` | Mismeasurement → wrong suggestion | B or C |
| `depth_processor` | Thickness error | B or C |
| `respiration_gating` | Misjudged stability | B or C |
| `exposure_recommender` | Wrong kVp/mAs suggestion | B or C |
| `operator_ui` | Operator misreads UI | B or C |
| `audit_logger` | Traceability loss | B |
| `device_gateway` | Generator control error | C (Phase 3) |

Confirm final classes with QA/RA before Phase 1 clinical use.

---

## Requirements Traceability

Every requirement must trace from user need to test evidence:

```
User Need (UN-xxx)
  └─► System Requirement (SYS-xxx)
        └─► Software Requirement (SW-xxx)
              └─► Architecture Component
                    └─► Test Case (TC-xxx)
                          └─► Test Result
                                └─► Risk Control Evidence
```

ID prefixes:

| Prefix | Type | Example |
|--------|------|---------|
| `UN` | User Need | UN-001: Operator can see breathing stability in real time |
| `SYS` | System Requirement | SYS-001: System measures chest motion at ≥ 30 Hz |
| `SW` | Software Requirement | SW-001: camera_service delivers 30 FPS depth stream |
| `HW` | Hardware Requirement | HW-001: Camera covers patient chest ROI at ≥ 95% |
| `RISK` | Risk Control | RISK-001: Disable recommendations on camera fault |
| `TC` | Test Case | TC-001: Verify UI warning on camera disconnect |

---

## Key Regulatory Risks

### Automatic Dose Determination

**Risk:** The system could be interpreted as making clinical exposure decisions.

**Mitigation:**
- UI labels suggestions as reference-only
- Operator approval is a hard gate, not a soft prompt
- Recommendation bounds are defined in a QA-approved LUT
- Source LUT version is logged with every suggestion

### X-ray Direct Control

**Risk:** Qualifies the device as X-ray control software, triggering electrical safety and EMC requirements.

**Mitigation:** Phase 1 has zero electrical connection to X-ray equipment. Phases 2 and 3 are separate product releases with dedicated risk analysis.

### Adaptive / Self-Learning

**Risk:** Post-deployment model changes without re-validation.

**Mitigation:** All models are pre-validated, signed offline, and gated by a Golden Test Suite before activation. On-device training is not in scope for any current phase.

---

## Cybersecurity

| Area | Requirement |
|------|-------------|
| Authentication | Role-based access (operator / admin / service) |
| Updates | Ed25519-signed packages only, rollback on failure |
| Data protection | No raw frames or PII stored; disk encryption on sensitive partitions |
| Network | Camera VLAN isolated from hospital network |
| Logging | Append-only audit log with hash chain |
| USB | USB mass storage disabled in production mode |
| SSH | Key-only access, password login disabled |

---

## Usability Checklist

| Scenario | Verified? |
|----------|:---------:|
| Camera recognition failure → operator can switch to manual | ☐ |
| Breath-hold fails → re-guidance path is clear | ☐ |
| Suggestion vs. confirmed value cannot be confused | ☐ |
| Emergency: bypass system and shoot manually within 10 s | ☐ |
| Pediatric/bariatric mode switch shows explicit warning | ☐ |

---

## Change Control

| Change Type | Impact | Required Action |
|-------------|--------|----------------|
| UI text edit | Low–Medium | Usability review |
| Camera SDK version | Medium | Regression test |
| Exposure LUT update | High | Risk analysis + validation + QA approval |
| AI model change | High | Signed release + golden test suite |
| Add X-ray control | Very High | New regulatory strategy |

---

## Release Gate Checklist

Before any clinical release:

- [ ] Requirements specification complete
- [ ] Software architecture document updated
- [ ] Risk management file current
- [ ] Verification test results documented
- [ ] Known issues list reviewed and accepted
- [ ] Installation and operation manual finalized
- [ ] Cybersecurity checklist signed off
- [ ] Software version and SBOM recorded
- [ ] Rollback plan tested
