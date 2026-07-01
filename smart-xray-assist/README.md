# Smart X-ray Assist — Phase 1 MVP (Operator Assist)

A reference-only "operator assist" overlay for plain-film X-ray. A depth camera
watches the patient's chest, the system measures thickness, detects a stable
breath-hold, and **suggests** (never sets) kVp/mAs from a signed lookup table.
Every suggestion requires explicit operator approval. **The system never fires
the X-ray** and never touches the machine's manual workflow — on any fault it
drops to a visible *Manual Mode* safe state.

This repo implements the design in [`en/files/*.md`](../en/files). It runs
end-to-end with **no hardware** via a synthetic (mock) depth camera.

> Status: Phase 1 MVP. All unit + integration tests green (42 passed). The
> RealSense path is import-guarded and only used on an edge board.

---

## Quick start

```bash
cd smart-xray-assist
python3 -m pip install -e ".[dev]"        # numpy, fastapi, jsonschema, pytest, httpx…

# 1) headless — drive the mock pipeline, print state once a second
python3 scripts/run_mvp.py --headless --seconds 10

# 2) server + operator console
python3 scripts/run_mvp.py                # http://localhost:8080/

# 3) daily empty-bed calibration check (GTS-002)
python3 scripts/calibrate_empty_bed.py --profile configs/calib_room_a.json

# 4) tests
python3 -m pytest tests/ -q
```

In the operator console: **Start Session → Play Breath Cue** (the mock simulates
a compliant patient holding their breath) → the state banner turns green
*READY* and a reference kVp/mAs card appears → **Approve**. **Abort** resumes
breathing; **Switch to Manual Mode** flips to the safe-state overlay.

---

## Architecture

Single-process pipeline wired through an in-process event bus. The bus mirrors
the production ZeroMQ contract (bounded queues, counted drops), so a later
transport swap is a bus change, not a service rewrite (tech-stack §10).

```
 camera_service ──frame──▶ depth_processor ──DepthSummary──▶ respiration_gating
 (mock|realsense)            (9-step pipeline)                (state machine)
        │                          │                                │
        └── camera.frame_meta      └── depth.summary        respiration.state
                              event bus                             │
                                   │                         (stable_breath_hold)
                                   ▼                                ▼
                              audit_logger ◀── all events    exposure_recommender
                          (SQLite WAL + SHA-256 chain)        (LUT + guardrails +
                                                               approval gate)
                                   │                                │
                                   └────────── FastAPI gateway ─────┘
                                        REST + WebSocket → operator console
```

| Module | File | Responsibility |
|--------|------|----------------|
| common | `common/{clock,messages,errors,event_bus,config,validation}.py` | message contracts, safe-state policy, signed-config gate, JSON-Schema validation |
| camera | `camera/{interface,mock_camera,realsense_adapter,service}.py` | vendor-agnostic depth frames; USB/frame-drop fault handling |
| depth | `depth/{calibration,processor}.py` | signed calibration + drift check; camera.md 9-step pipeline → thickness |
| gating | `gating/respiration.py` | dZ/dt + d²Z/dt² state machine, cough abort |
| exposure | `exposure/recommender.py` | LUT lookup, guardrail clamp, **operator approval gate** |
| audit | `audit/logger.py` | append-only SQLite (WAL) + SHA-256 hash chain |
| app | `app.py` | orchestrator: wiring, session, safe-state, operator actions |
| api | `api/gateway.py` | FastAPI REST + `/ws/v1/events` WebSocket |

---

## Respiration gating (the breath-hold detector)

The depth signal is differentiated twice: velocity `dZ/dt` (motion) and
acceleration `d²Z/dt²` (cough/jerk). A cough spikes the acceleration channel and
forces `abort` even before velocity crosses its threshold (camera.md).

Naive differentiation of the raw depth signal explodes the acceleration channel
and false-aborts every frame, because the signal carries three noise sources the
second derivative amplifies:

1. **Sensor quantization** — the Z16 depth stream is integer-millimetre, so the
   ROI **median** stair-steps in 1 mm jumps. The gating signal therefore uses
   the **mean** over valid (hole-free) ROI pixels, which is sub-mm smooth; the
   median stays the hole-robust headline for *thickness*.
2. **Acquisition jitter** — per-frame timestamp deltas vary ±25%; dividing finite
   differences by a jittery `dt` injects acceleration noise. `dt` is EMA-smoothed
   to the true cadence.
3. **Residual sensor noise** — `z` and `dz/dt` are EMA-smoothed (camera.md step-7
   temporal filter) before differencing, and the cough abort is suppressed for a
   short warm-up while the filters converge.

Result: normal breathing peaks at ~20 mm/s² (< 25 threshold, no false abort), a
cough hits >1000 mm/s² (aborts cleanly). Tunables live in
[`configs/gating.yaml`](configs/gating.yaml). The filters are tuned for the
configured camera fps (`configs/camera.yaml`); `run_mvp` drives at `1/fps`.

---

## Safety model

- **Never fires the X-ray.** Recommendations are reference-only; every one carries
  `operator_approval_required: true`.
- **Guardrails** clamp any LUT value to a safe kVp/mAs range; clamped values are
  flagged to the UI.
- **Manual review** modes (pediatric/bariatric LUT rows flagged "pending clinical
  review") return *no numbers* — the UI shows only a manual-review notice.
- **Safe state** on any fault (camera disconnect, frame-drop spike, calibration
  drift/missing, low confidence, DB write failure, invalid signature): the
  overlay disables recommendations and flips the console to *Manual Mode*. The
  X-ray machine's own manual workflow is untouched.
- **Signed configs/calibration** — an unsigned or mismatched file blocks startup.
  (MVP ships an HMAC placeholder behind the production Ed25519 interface.)
- **Tamper-evident audit** — append-only SQLite with a SHA-256 hash chain;
  `verify_chain()` recomputes every link.

---

## Tests

Mapped to [`verification-validation.md`](../en/files/verification-validation.md).

```bash
python3 -m pytest tests/unit/ -v          # UT-*
python3 -m pytest tests/integration/ -v   # IT-*
```

| ID | What it proves |
|----|----------------|
| UT-LUT-001 | LUT boundaries + guardrail min/max clamping |
| UT-GATE-001 | dZ/dt stable vs unstable classification |
| UT-GATE-002 | cough spike detected, normal breathing not |
| UT-SCHEMA-001 | missing required fields caught |
| UT-AUDIT-001 | single-entry tampering detected |
| UT-CONFIG-001 | invalid YAML blocked on load |
| UT-CONF-001 | every `confidence` field ∈ [0,1] |
| IT-CAM-CORE-001 | frame_meta published, parsed, schema-valid |
| IT-CORE-UI-001 | UI receives respiration state < 200 ms |
| IT-AUDIT-001 | operator action persisted with valid hash |
| IT-SAFE-001 | error → safe state, recommendations disabled |

Fault-injection (FI-*) and the hardware Golden Test Suite (GTS-*) run against a
real board and are out of scope for the no-hardware MVP, except where covered
above (GTS-002 calibration, GTS-005/006/007).

---

## REST / WebSocket API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | service health + uptime |
| GET | `/api/v1/state` | session / camera / calibration / respiration / safe-state |
| POST | `/api/v1/sessions` | start a session `{body_region, patient_mode}` |
| POST | `/api/v1/operator/approve` | approve a recommendation |
| POST | `/api/v1/operator/action` | `play_breath_cue` \| `switch_manual_mode` \| `abort` \| … |
| WS | `/ws/v1/events` | live `depth.summary` / `respiration.state` / `exposure.recommendation` / `system.error` |

Local only — never reaches an external network. Messages are validated against
[`schemas/*.schema.json`](schemas).

---

## Configuration

`configs/` — `device.yaml`, `camera.yaml` (provider `mock`|`realsense`|…),
`gating.yaml`, `exposure_lut.yaml`, `calib_room_a.json`. Switching cameras is a
config change (`camera.yaml: provider`), not a code change.

## en vs Ko docs

Implementation follows **`en/files`**. The `Ko/` folder is *not* a 1:1
translation — it drops the Golden Test Suite / audio-latency sections, remaps
fault-injection IDs, and omits some LUT rows. Treat `en/` as the source of truth.
