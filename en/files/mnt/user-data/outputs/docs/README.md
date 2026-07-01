# Documentation Index

Start with the [project README](../README.md) for the tech stack overview and architecture diagram.

---

## Docs

| Document | What you'll find |
|----------|-----------------|
| [`camera.md`](camera.md) | Camera selection rationale, SDK installation, wiring, the full depth processing pipeline, respiration state machine, calibration procedures |
| [`hardware.md`](hardware.md) | Board selection, USB/PoE wiring, power design, X-ray integration hardware phases, mounting requirements, thermal limits |
| [`api-schema.md`](api-schema.md) | Every inter-service message schema (CameraFrameMeta, DepthSummary, RespirationState, ExposureRecommendation, AuditEvent), REST endpoints, WebSocket events |
| [`deployment.md`](deployment.md) | systemd service configuration, offline update procedure, security hardening, operations monitoring, fault runbook |
| [`tech-stack-assessment.md`](tech-stack-assessment.md) | Vendor status per component, known issues, risk matrix, recommended actions — review quarterly |
| [`risk-management.md`](risk-management.md) | ISO 14971 hazard list, risk controls, safe-state definition, fault injection test map, traceability |
| [`regulatory.md`](regulatory.md) | IEC 62304 / ISO 13485 approach, software safety class rationale, cybersecurity, change control, release gate |
| [`verification-validation.md`](verification-validation.md) | Test strategy, phantom test specs, fault injection procedures, audio latency measurement, Golden Test Suite, acceptance criteria |

---

## File Structure

```
project-root/
  README.md
  docs/
    README.md               ← you are here
    camera.md
    hardware.md
    api-schema.md
    deployment.md
    tech-stack-assessment.md
    risk-management.md
    regulatory.md
    verification-validation.md
  services/
  ui/
  configs/
  models/
  schemas/
  tests/
  scripts/
  deploy/
```

---

## Korean source documents

Original Korean documents are preserved with `_ko` suffix:

| English | Korean original |
|---------|----------------|
| `README.md` | `readme_v6_dev_stack_ko.md` |
| `docs/camera.md` | `camera_v3_integration_ko.md` |
| `docs/api-schema.md` | `api-schema_ko.md` |
| `docs/deployment.md` | `deployment_ko.md` |
| `docs/hardware.md` | `hardware_ko.md` |
| `docs/regulatory.md` | `regulatory_ko.md` |
| `docs/risk-management.md` | `risk-management_ko.md` |
| `docs/verification-validation.md` | `verification-validation_ko.md` |
| `docs/tech-stack-assessment.md` | `tech-stack-assessment_ko.md` |
