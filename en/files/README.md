# Smart X-ray Assist

> Depth-sensor-driven breathing gating and body thickness measurement for X-ray positioning assistance.

A real-time edge system that watches a patient's chest with a 3D depth camera, detects stable breath-hold moments, estimates body thickness, and surfaces a suggested kVp/mAs on the operator's display — without ever touching the X-ray generator. The operator reviews everything and presses shoot.

**What it is not**: an autonomous exposure controller, a diagnostic AI, or a drop-in AEC replacement.

---

## Tech Stack

### Hardware

| Role | MVP | Production Candidate |
|------|-----|----------------------|
| Depth camera | Intel RealSense D455 (USB 3.x) | Orbbec Femto Mega I (PoE) |
| Edge board | Raspberry Pi 5 8 GB | Jetson Orin Nano 8 GB / Super |
| AI accelerator | — | Hailo-8 via AI HAT+ (RPi) · Jetson CUDA/TensorRT |
| Audio | USB speaker (GStreamer + ALSA) | Same |
| Display | HDMI + Chromium kiosk | HDMI + Qt/QML |
| Storage | NVMe SSD (256 GB+) | Same |
| OS | Ubuntu 22.04 ARM64 | Ubuntu 22.04 LTS (pinned kernel) |

### Core Services

| Service | Language | Role |
|---------|----------|------|
| `camera_service` | C++20 | Vendor SDK wrapper, frame publish to shared memory |
| `depth_processor` | C++20 | Empty-bed correction, ROI extraction, thickness calc |
| `respiration_gating` | C++20 | dZ/dt stability detection, audio cue timing |
| `exposure_recommender` | C++20 / Rust | LUT lookup, safety clamp, operator-approval gate |
| `api_gateway` | Go | REST + WebSocket for operator UI |
| `audit_logger` | Go / Python | Append-only SQLite log with SHA-256 hash chain |
| `device_gateway` | C++20 / Rust | Phase 2+: isolated process for workstation autofill |

### Runtime & Libraries

| Layer | Choice | Notes |
|-------|--------|-------|
| Camera SDKs | librealsense 2.x (RSUSB), Orbbec SDK v2, DepthAI v3 | Abstracted behind `IDepthCamera` |
| AI inference | TensorRT 10.x (Jetson), ONNX Runtime CPU EP (RPi) | Hailo HEF optional on RPi |
| IPC (frames) | POSIX `memfd_create` + lock-free SPSC ring buffer | ~100 MB/s, no-copy |
| IPC (events) | ZeroMQ PUB/SUB (MVP) → NNG (production) | Depth summaries, state events |
| API framework | Go `net/http` + gorilla/websocket | Replaces FastAPI after MVP |
| Database | SQLite WAL + app-level hash chain | Audit log, calibration profiles |
| UI | React + TypeScript (MVP kiosk) → Qt/QML (production) | Runs locally, no external network |
| Build (C++) | CMake + Conan/vcpkg, Debian packages | Offline-installable |
| Config | YAML + JSON Schema + Ed25519 signature | Per-hospital profiles |
| Deployment | systemd services + signed offline update bundle | Air-gapped hospital networks |

### Language Strategy

```
MVP ──────────► Python (prototyping, tooling, tests)
                C++20  (camera_service, real-time pipeline)
                Go     (api_gateway, audit_logger)

Phase 2+ ─────► C++20  (everything real-time)
                Rust   (device_gateway, exposure_recommender)
                        └─ Ferrocene compiler: IEC 62304 Class C qualified
```

---

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      Edge Board                          │
│                                                          │
│  [3D Depth Camera]                                       │
│       │ USB 3.x / PoE Ethernet                          │
│       ▼                                                  │
│  camera_service  ──(shared memory ring buffer)──►        │
│                       depth_processor                    │
│                            │ ZeroMQ / NNG                │
│                       respiration_gating                 │
│                            │                             │
│                       exposure_recommender               │
│                            │                             │
│  ┌────────────────────────┴────────────────────────┐    │
│  │              api_gateway (Go)                    │    │
│  │   REST /api/v1/*   WebSocket /ws/v1/events       │    │
│  └──────────────────────────────────────────────────┘    │
│       │ WebSocket                    │ audit events       │
│  [Operator UI]               [audit_logger → SQLite]     │
│                                                          │
│  [device_gateway]  ← Phase 2+ only, isolated process     │
└──────────────────────────────────────────────────────────┘
              │ Phase 2+: TCP/gRPC
         [Workstation Agent]
              │ Phase 3+: RS-422 / CAN / GPIO (isolated)
         [X-ray Generator]
```

Operator actions (approve / reject / abort / manual mode) are logged to the audit chain before anything happens downstream.

---

## Phases

| Phase | What ships | X-ray control |
|-------|-----------|---------------|
| **1 — Operator Assist** | Thickness + breathing state on display, suggested kVp/mAs | None — operator types it in |
| **2 — Workstation Agent** | Auto-fill on X-ray console software | Indirect (operator must approve) |
| **3 — Generator Interface** | Direct parameter write via RS-422/CAN | Direct (hard interlocks required) |
| **4 — Controlled Model Update** | Signed, validated model rollout | N/A |
| **5 — On-device Learning** | Offline-trained models, signed + golden-test gated | N/A |

Everything beyond Phase 1 is a separate release with its own risk file and regulatory review.

---

## Quick Start (MVP — RealSense D455 on RPi 5 or Jetson)

### 1. System dependencies

```bash
sudo apt update && sudo apt install -y \
  build-essential cmake ninja-build pkg-config git \
  libopencv-dev libeigen3-dev libssl-dev sqlite3 jq \
  gstreamer1.0-tools alsa-utils python3-venv
```

### 2. Install librealsense (RSUSB backend — no kernel patch)

```bash
git clone https://github.com/realsenseai/librealsense.git
cd librealsense && mkdir build && cd build
cmake .. -DBUILD_EXAMPLES=ON \
         -DBUILD_PYTHON_BINDINGS=ON \
         -DFORCE_RSUSB_BACKEND=ON
make -j$(nproc) && sudo make install
```

Verify:

```bash
rs-enumerate-devices -s   # confirm USB 3.x speed, not USB 2.0
```

### 3. Python PoC environment

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install numpy opencv-python fastapi uvicorn pydantic pyzmq pytest
```

### 4. Run camera_service (Python PoC)

```bash
python services/camera_service/camera_service.py \
  --config configs/camera_profile.d455.yaml
```

### 5. Empty-bed calibration

```bash
python scripts/calibrate_empty_bed.py --output configs/calib_room_a.json
```

The resulting calibration file is signed and recorded in the audit log at startup.

---

## Development Setup (Jetson Orin Nano)

```bash
# Confirm JetPack version
cat /etc/nv_tegra_release

# Check TensorRT (must be 10.x for JetPack 6.x)
python3 -c "import tensorrt as trt; print(trt.__version__)"

# Convert ONNX model to TRT engine (fp16)
trtexec \
  --onnx=models/stable_breathhold.onnx \
  --saveEngine=models/stable_breathhold_jp62_trt103_fp16.engine \
  --fp16

# Monitor temps during long-run tests
tegrastats --interval 5000
```

> **Note on `jetson_clocks`**: use it for benchmarking only. Production boards use `nvpmodel` profiles — set once in `configs/device.yaml` and leave it.

---

## Repository Layout

```
smart-xray-assist/
├── README.md
├── CMakeLists.txt
├── configs/
│   ├── device.yaml
│   ├── camera_profile.d455.yaml
│   ├── camera_profile.orbbec.yaml
│   ├── gating.yaml
│   └── exposure_lut.yaml
├── schemas/
│   ├── config.schema.json
│   ├── audit_event.schema.json
│   └── depth_summary.schema.json
├── services/
│   ├── camera_service/
│   │   ├── adapters/
│   │   │   ├── realsense_adapter.cpp
│   │   │   ├── orbbec_adapter.cpp
│   │   │   └── depthai_adapter.cpp
│   │   └── include/IDepthCamera.h      ← vendor-agnostic interface
│   ├── depth_processor/
│   ├── respiration_gating/
│   ├── exposure_recommender/
│   ├── api_gateway/
│   ├── audit_logger/
│   └── device_gateway/                 ← Phase 2+
├── ui/
│   └── operator-console/               ← React/TS (MVP)
├── models/
│   ├── manifest.json
│   └── *.onnx / *.engine
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── playback/
│   └── hil/
├── scripts/
│   ├── calibrate_empty_bed.py
│   ├── install_realsense.sh
│   └── export_onnx_to_trt.sh
└── deploy/
    ├── systemd/
    ├── offline-update/
    └── scripts/
```

---

## Documentation

| Doc | What's in it |
|-----|-------------|
| [`docs/camera.md`](docs/camera.md) | Camera selection rationale, SDK install, data pipeline, calibration |
| [`docs/hardware.md`](docs/hardware.md) | Board specs, power design, X-ray integration hardware, mounting |
| [`docs/api-schema.md`](docs/api-schema.md) | All internal message schemas, WebSocket events, REST endpoints |
| [`docs/deployment.md`](docs/deployment.md) | systemd config, offline update, rollback, ops runbook |
| [`docs/tech-stack-assessment.md`](docs/tech-stack-assessment.md) | Vendor status, known issues per component, risk matrix |
| [`docs/risk-management.md`](docs/risk-management.md) | ISO 14971 hazard list, risk controls, safe-state definition |
| [`docs/regulatory.md`](docs/regulatory.md) | IEC 62304 / ISO 13485 approach, software safety class, change control |
| [`docs/verification-validation.md`](docs/verification-validation.md) | Test strategy, phantom tests, fault injection, acceptance criteria |

---

## Safety in One Paragraph

The system never fires the X-ray. In Phase 1 it shows numbers on a screen; a licensed radiographer reads them and decides. Every recommendation is bounded by a pre-approved LUT with hard kVp/mAs limits. If the camera drops, calibration expires, or confidence falls below threshold, the UI goes dark and flashes **Manual Mode** — the existing X-ray workflow continues unaffected. Every operator action, approval, abort, and model version is written to an append-only audit log with a SHA-256 hash chain before it has any effect.

---

## License

See `LICENSE`. This repository does not constitute a cleared medical device. Refer to [`docs/regulatory.md`](docs/regulatory.md) before any clinical deployment.
