# Exposure recommendation & safety

[← back to README](../README.md) · [한국어](exposure-and-safety.ko.md)

## Exposure recommendation (LUT + guardrails)

[`exposure/recommender.py`](../smart-xray-assist/src/xray_assist/exposure/recommender.py) · [`configs/exposure_lut.yaml`](../smart-xray-assist/configs/exposure_lut.yaml)

Once a stable breath-hold is detected, the **estimated thickness + body region + patient mode** are looked up in a signed table for kVp/mAs.

```
thickness(mm) + body_region(chest_pa) + mode(adult|pediatric|bariatric)
        └→ LUT row → kVp/mAs → guardrail clamp → recommendation
```

### LUT (v1.3.0, signed)

| Mode | Thickness (mm) | kVp | mAs | Note |
|---|---|---|---|---|
| adult | 0–180 | 70 | 8.0 | |
| adult | 181–240 | 82 | 15.0 | |
| adult | 241–320 | 90 | 22.0 | |
| pediatric | 0–120 | 60 | 4.0 | pending clinical review |
| bariatric | 321–450 | 100 | 40.0 | pending clinical review |

- **Signed (`signed: true`)**: the LUT is QA-approved and Ed25519-signed offline; only integrity-verified tables are used. Each recommendation carries the source (`lut_v1.3.0`) and a `model_hash` (SHA-256 of the model file) for traceability.
- **Pending-review rows**: if the thickness lands on a review-pending row, there is **no automatic recommendation** → `manual_review_required=true`. The console shows a "Manual review required" message instead of kVp/mAs.

### Guardrail clamp

Even a valid LUT value is clamped to a physical safety range:

```
kVp ∈ [60, 120]      mAs ∈ [1.0, 80.0]
```

A clamp sets `within_min_max=false` on the recommendation, and the console shows a "Clamped" badge. This is risk control **RC-EXP-001** (recommendations must not exceed LUT bounds); **RC-EXP-002** requires confidence + LUT version on every recommendation.

---

## Safety model

### Reference-only

A recommendation is a **suggestion**, never auto-applied:

```
recommendation emitted → operator reviews → explicit approval (POST /operator/approve) → audit record
                                                  └→ the operator applies it in the X-ray machine's own manual workflow
```

The system neither fires the X-ray nor sets any generator parameter. Approval is only an audit record that says "I saw and accept this reference value." Operator approval is a **hard gate, not a soft prompt** (RC-UI-004).

### Fail-to-manual (safe state)

On any fault the system falls to Manual Mode and disables recommendations. Triggers (from the risk analysis) include: camera disconnected/not found · consecutive frame drops over threshold · calibration missing/expired/invalid signature · ROI detection failed · confidence below minimum · patient motion/cough · recommender exception · model/config signature invalid · DB write failure or storage full.

Safe-state behaviour:

- exposure recommendations disabled
- all automated/semi-automated inputs disabled
- operator directed to the manual X-ray workflow
- audit event recorded, audio guidance stopped
- **the X-ray machine's own manual workflow is never touched** — if this system dies, imaging proceeds as usual
- transient faults auto-clear when a good frame returns

The full safe-state code list is in the [architecture doc](architecture.md#safe-state-manual-mode).

### Approval gating

- `manual_review_required` recommendations disable the approve button
- safe state blocks all approvals
- only an approved `recommendation_id` is honoured by `is_approved()`

### Regulatory justification (summary)

Phase 1's reference-only posture and **zero electrical connection** to the X-ray equipment keep it out of higher electrical-safety scope. UI labels all suggestions "Reference-only — operator confirmation required," suggested vs. confirmed values are visually distinct (RC-UI-001), and manual override is always accessible (RC-UI-002). Details: [Safety, risk & regulatory](safety-risk-regulatory.md).

Related: [Audit hash chain](audit-chain.md) · [Depth & gating](depth-and-gating.md)
