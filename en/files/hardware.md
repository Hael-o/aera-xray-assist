# Hardware Design

Edge compute, camera mounting, power, electrical isolation, and X-ray integration hardware — from MVP breadboard to production.

---

## Overview

```
[3D Depth Camera]
      │ USB 3.x or PoE/Ethernet
      ▼
[Edge Compute Board]
      ├─ camera_service
      ├─ depth_processor
      ├─ respiration_gating
      ├─ exposure_recommender
      ├─ audit_logger
      └─ device_gateway (Phase 2+)
      │
      ├─ HDMI/DP ─────────────► Operator Display
      ├─ USB Audio / 3.5mm ───► Speaker
      ├─ GPIO / RS-422 / CAN ─► X-ray Integration (Phase 3)
      └─ Ethernet ────────────► Workstation Agent (Phase 2+)
```

---

## Board Selection

| Stage | Board | Camera | Connection | Notes |
|-------|-------|--------|------------|-------|
| MVP | RPi 5 8 GB or Jetson Orin Nano | D455 | USB 3.x | Fast to set up |
| Installed PoC | Jetson Orin Nano 8 GB | Femto Mega I | PoE | Ceiling mount, long-run stability |
| Production | Jetson Orin Nano Industrial or industrial x86 | PoE depth camera | PoE/Ethernet | Power, thermals, recovery |
| Low-power | RPi 5 + AI HAT+ or OAK-D Pro PoE | OAK-D Pro PoE | PoE | Camera-side ROI inference |

### Raspberry Pi 5 8 GB

Good for MVP. Handles D455 frame collection, rule-based gating, UI, and logging without breaking a sweat on a single workload. Start feeling the pressure when you add TensorRT-class inference.

| Item | Spec |
|------|------|
| Board | RPi 5 8 GB |
| OS | RPi OS 64-bit or Ubuntu 22.04 ARM64 |
| Storage | NVMe SSD (SD card for PoC only) |
| AI Acceleration | AI HAT+ 13/26 TOPS — inference only, not a camera driver |
| Cooling | Active cooler — non-negotiable for 8-hour runs |

**Do not** use a cheap USB hub between the D455 and the board. The camera is power-hungry and prone to USB 2.0 fallback on marginal connections.

### Jetson Orin Nano 8 GB / Super

The right choice once you need TensorRT inference, C++ pipelines, or multi-camera setups.

| Item | Spec |
|------|------|
| Board | Jetson Orin Nano 8 GB (or Super with JetPack 6.2) |
| OS/BSP | JetPack 6.x, Ubuntu 22.04 |
| AI Runtime | TensorRT 10.x, CUDA 12.x, ONNX Runtime TensorRT EP |
| Storage | NVMe SSD 256 GB+ |
| Cooling | PWM fan + heatsink + temp monitoring |

Pin the JetPack version. CUDA/TensorRT/cuDNN in JetPack are a matched set — arbitrary upgrades break things. Use `nvpmodel` for power profiles in production, not `jetson_clocks`.

**Checking temperatures:**

```bash
# Jetson
tegrastats
sudo nvpmodel -q
sudo jetson_clocks --show

# RPi
vcgencmd measure_temp
vcgencmd get_throttled
```

---

## Camera Connections

Full SDK install and pipeline detail is in [`docs/camera.md`](camera.md). This section covers physical wiring only.

### RealSense D455 — USB 3.x

```
[D455] ─── USB 3.x cable ─── Edge board USB 3.x port
```

- Direct port connection, no passive hub.
- Shielded cable, fixed bracket near X-ray equipment.
- Cable ≤ 1 m preferred; active repeater for ≥ 3 m.
- Verify USB 3.x speed at boot — silent fallback to USB 2.0 causes frame drops.

### Orbbec Femto Mega I — PoE

```
[Femto Mega I] ─── Cat6 ─── PoE Switch ─── Edge board Ethernet
```

Camera network is isolated from hospital HIS/PACS. Static IP assignment. Check PoE budget — camera draws ~10–15 W.

```
Camera VLAN:  192.168.50.0/24
Camera IP:    192.168.50.10
Edge board:   192.168.50.2
Gateway:      none (isolated)
```

### Luxonis OAK-D Pro PoE

Same physical wiring as Femto. Different software: you push a pipeline to the camera's VPU and receive processed results back, not raw frames.

---

## Audio Output

Breathing guidance timing is latency-sensitive. Minimize OS mixer layers.

| Option | Recommended | Notes |
|--------|:-----------:|-------|
| USB Audio DAC | ✓ | Low noise, easy to replace |
| 3.5mm analog | PoC | Board-dependent noise floor |
| HDMI audio | ✗ | Display dependency |
| ALSA direct | ✓ | Minimizes latency variance |
| PulseAudio / PipeWire | PoC | Validate latency variance |

```bash
# GStreamer direct ALSA example
gst-launch-1.0 \
  filesrc location=hold_breath.wav ! \
  wavparse ! audioconvert ! audioresample ! \
  alsasink device=hw:1,0
```

Measure the actual audio latency at installation. Set `audio_latency_offset_ms` in `gating.yaml` accordingly — see [`docs/verification-validation.md`](verification-validation.md#audio-latency-measurement).

---

## X-ray Integration Hardware

### Phase 1 — Operator Assist (current)

No electrical connection to X-ray equipment. The system shows numbers; the operator types them in.

### Phase 2 — Workstation Agent

```
[Edge board] ─── TCP/gRPC ─── [Workstation Agent] ─── X-ray console API
```

Software only. The agent must confirm operator approval before writing to the console. UI automation (screen scraping the console software) is fragile — get the manufacturer's API.

### Phase 3 — Generator Direct Control

```
[Edge board] ─── [Isolated Interface Board] ─── X-ray Generator
                   RS-422 / CAN / Ethernet / GPIO relay
```

**Prerequisites before Phase 3 starts:**
- Manufacturer protocol documentation
- Galvanic isolation circuit design and sign-off
- fail-safe default state defined
- Watchdog + interlock + emergency abort path
- Medical electrical safety and EMC testing plan
- Operator approval independent of software interlock

### Isolation Board Requirements

| Item | Requirement |
|------|-------------|
| Galvanic isolation | Controller and X-ray circuit must be electrically separated |
| Signal isolation | Opto-isolator or digital isolator |
| Output device | Relay or SSR matched to equipment input spec |
| Surge protection | TVS diode, fuse, current limit |
| Fail-safe | Open state on power loss or process fault |
| Watchdog | Output disabled on heartbeat loss |
| Manual override | Always takes priority over software |
| EMC | Design to meet emission/immunity requirements |

Never describe any design as "100% safe" or "no certification required." The specification is that isolation voltage, leakage current, creepage, clearance, and EMC requirements are **met by design and verified by test**.

---

## Power Design

```
[Medical-grade AC adapter or isolated DC supply]
  ├─ Edge board
  ├─ Camera / PoE switch
  ├─ Audio amplifier
  └─ Interface board (Phase 3)
```

Validate power resilience:

| Test | Expected result |
|------|----------------|
| Momentary power cut | Safe state, no trigger |
| PoE link renegotiation | Camera service auto-reconnects |
| USB voltage drop | Error log, UI warning, manual mode |
| Edge board reboot | systemd services auto-recover |

---

## Mounting

**Camera position:**
- Fixed mount above the patient table, within D455/Femto field of view for chest ROI.
- Clear of the X-ray beam path.
- No collision risk with patient or operator.
- Alcohol-disinfection resistant housing or protective cover.
- Adequate heat dissipation clearance.

**Calibration hardware (have these on site):**
- Flat calibration plate (for extrinsic calibration)
- Known-height phantom blocks (50 mm, 100 mm, 200 mm)
- Breathing phantom (step-motor driven, ±5–50 mm range)
- Table-origin measurement jig

---

## Thermal Limits

| Item | Target |
|------|--------|
| Edge board temp | ≤ 70 °C sustained |
| Camera temp | Within manufacturer spec |
| Fan control | PWM auto or fixed profile |
| Temp logging | 1-minute interval minimum |
| Throttling | UI warning + log on detection |

---

## Hardware Bring-up Checklist

| Step | Check | Pass criteria |
|------|-------|---------------|
| 1 | Board boots | OS starts, SSH/console accessible |
| 2 | Camera recognized | SDK enumerates device |
| 3 | Depth stream | ≥ 30 FPS stable |
| 4 | Audio output | Latency measured, audible |
| 5 | UI display | HDMI renders correctly |
| 6 | Database | SQLite WAL writes correctly |
| 7 | Watchdog | Service crash triggers restart |
| 8 | PoE camera | Static IP connected |
| 9 | Calibration | Empty-bed origin measured |
| 10 | Safe mode | Camera fault → recommendations disabled |

---

## Pre-Production Hardware Validation

- 8-hour continuous frame-drop test
- 24-hour burn-in
- USB/PoE cable plug/unplug cycle test
- Board reboot + camera reconnect test
- Temperature ramp test
- Room lighting interference test
- X-ray equipment EMI observation
- Patient gown / metal reflector effect on depth quality
- Re-calibration repeatability after physical disturbance
